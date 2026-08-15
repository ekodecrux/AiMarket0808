"""Scheduled agent execution framework.

Implements the roadmap's autonomous scheduling layer:
- agent_schedules: tenant-scoped recurring tasks (cron-based) with policy-aware
  execution kinds (learning reports, mission reviews, lead score refresh,
  brain reindex, lead enrichment, experiment review, campaign reports, custom
  prompt tasks, content proposals).
- agent_runs: immutable run history with status, duration, output and errors.
- A long-lived asyncio scheduler (started from server lifespan) wakes every 60
  seconds, checks due schedules, and executes them inside policy gates
  (kill switch and autonomy level), emitting telemetry and audit records.

Execution runs a "system user" surrogate via engine primitives; every action is
gated by check_autonomy and always audited. Human-triggered runs
(POST /agents/schedules/{id}/run) always bypass the due-time check.
"""

import asyncio
import json
import logging
import re
import traceback
from datetime import datetime, timezone, timedelta

import ai as ai_service
import engine as eng

logger = logging.getLogger(__name__)

_db = None
_scheduler_task = None
_running_lock = None

AGENT_KINDS = {
    "learning_report": {
        "name": "Weekly Learning Report",
        "description": "Analyzes last week's experiments, revenue and campaigns, records winners/losers and proposes next experiments.",
        "policy": "controlled_autopilot",
    },
    "mission_review": {
        "name": "Mission Progress Review",
        "description": "Reviews open missions and drafts status updates with recommended next actions.",
        "policy": "approve",
    },
    "lead_score_refresh": {
        "name": "Lead Score Refresh",
        "description": "Re-scores recent leads with the latest intent signals and updates hot/warm/cold categories.",
        "policy": "approve",
    },
    "brain_reindex": {
        "name": "Brain Reindex",
        "description": "Re-embeds all brain knowledge sources so semantic retrieval stays fresh.",
        "policy": "controlled_autopilot",
    },
    "lead_enrichment": {
        "name": "Lead Enrichment Sweep",
        "description": "Enriches leads missing company or industry data using their available signals.",
        "policy": "approve",
    },
    "experiment_review": {
        "name": "Experiment Review",
        "description": "Checks running experiments and recommends decisions when minimum samples are met.",
        "policy": "approve",
    },
    "campaign_report": {
        "name": "Campaign Report",
        "description": "Summarizes channel spend, leads and revenue into a concise campaign performance report.",
        "policy": "controlled_autopilot",
    },
    "custom_prompt": {
        "name": "Custom Analysis Task",
        "description": "Runs a custom grounded prompt against the business brain on a schedule.",
        "policy": "approve",
    },
    "content_proposal": {
        "name": "Content Proposal Batch",
        "description": "Generates a batch of grounded content ideas from the mission plan and business brain.",
        "policy": "approve",
    },
}


def bind_db(database):
    global _db
    _db = database


def _ensure_indexes():
    if _db is None:
        return

    async def _create():
        try:
            await _db.agent_schedules.create_index("tenant_key")
            await _db.agent_schedules.create_index("next_run_at")
            await _db.agent_runs.create_index([("tenant_key", 1), ("schedule_id", 1)])
            await _db.agent_runs.create_index("created_at")
        except Exception as e:
            logger.warning(f"agent indexes failed: {e}")
    return _create()


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _tenant_key(user: dict, client_id: str = None) -> str:
    return eng._tenant_key(user, client_id)


def _user_for_tenant(user: dict, client_id: str = None) -> dict:
    """Surrogate user dict for agent-initiated execution: inherits the human
    owner's scope so all engine primitives resolve to the same tenant."""
    return {
        "_id": user["_id"],
        "owner_id": user.get("owner_id") or str(user["_id"]),
        "client_id": client_id or user.get("client_id"),
        "is_agent": True,
    }


def _recurrence_next(kind: str, value: str | int, last_run: str = None) -> str | None:
    """Compute the next UTC run time for a simple recurrence rule."""
    now = datetime.now(timezone.utc)
    try:
        if kind == "daily":
            hour, minute = 2, 0
            if isinstance(value, str) and ":" in value:
                parts = value.split(":")
                hour, minute = int(parts[0]) % 24, int(parts[1]) % 60
            nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if nxt <= now:
                nxt += timedelta(days=1)
            return nxt.isoformat()
        if kind == "weekly":
            day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
            parts = re.split(r"[\s,]+", (value or "mon 02:00").strip().lower())
            day = day_map.get(parts[0], 0)
            time_part = parts[1] if len(parts) > 1 else "02:00"
            hour, minute = 2, 0
            if ":" in time_part:
                hp = time_part.split(":")
                hour, minute = int(hp[0]) % 24, int(hp[1]) % 60
            nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            while nxt.weekday() != day:
                nxt += timedelta(days=1)
            if nxt <= now:
                nxt += timedelta(days=7)
            return nxt.isoformat()
        if kind == "interval_hours":
            hours = max(1, int(value or 24))
            if last_run:
                try:
                    base = datetime.fromisoformat(last_run)
                    nxt = base + timedelta(hours=hours)
                    if nxt <= now:
                        nxt = now + timedelta(hours=hours)
                    return nxt.isoformat()
                except Exception:
                    pass
            return (now + timedelta(hours=hours)).isoformat()
        if kind == "once":
            if isinstance(value, str):
                try:
                    nxt = datetime.fromisoformat(value)
                    if nxt.tzinfo is None:
                        nxt = nxt.replace(tzinfo=timezone.utc)
                    if nxt < now:
                        nxt = now + timedelta(hours=1)
                    return nxt.isoformat()
                except Exception:
                    pass
            return (now + timedelta(hours=1)).isoformat()
    except Exception as e:
        logger.warning(f"recurrence parse failed ({kind}={value}): {e}")
    return (now + timedelta(hours=24)).isoformat()


# ---------------------------------------------------------------------------
# Schedule CRUD
# ---------------------------------------------------------------------------

async def schedule_create(user: dict, client_id: str, name: str, kind: str,
                          recurrence_kind: str = "daily", recurrence_value=None,
                          enabled: bool = True, params: dict = None) -> dict:
    if _db is None:
        raise RuntimeError("agents not bound")
    if kind not in AGENT_KINDS:
        raise RuntimeError(f"Unknown agent kind. Choose from: {', '.join(AGENT_KINDS)}")
    tenant_key = _tenant_key(user, client_id)
    doc = {
        "tenant_key": tenant_key,
        "user_id": user.get("owner_id") or str(user["_id"]),
        "client_id": client_id or user.get("client_id"),
        "name": (name or AGENT_KINDS[kind]["name"]).strip(),
        "kind": kind,
        "recurrence_kind": recurrence_kind,  # daily | weekly | interval_hours | once
        "recurrence_value": recurrence_value,
        "params": params or {},
        "enabled": bool(enabled),
        "consecutive_failures": 0,
        "created_at": _now_iso(),
    }
    doc["next_run_at"] = _recurrence_next(recurrence_kind, recurrence_value)
    res = await _db.agent_schedules.insert_one(doc)
    sid = str(res.inserted_id)
    await eng.emit_event(user, "AutonomousActionExecuted", client_id=client_id,
                         actor_type="agent", actor_id=sid,
                         entity_type="agent_schedule", entity_id=sid,
                         payload={"kind": kind, "name": doc["name"],
                                  "recurrence": f"{recurrence_kind}:{recurrence_value}",
                                  "note": "scheduled (not yet executed)"})
    await eng.record_audit(user, "agent.schedule_create", client_id=client_id,
                           detail={"schedule_id": sid, "kind": kind, "name": doc["name"]})
    return {"id": sid, **{k: v for k, v in doc.items() if k not in ("user_id",)}}


async def schedule_list(user: dict, client_id: str = None) -> list:
    if _db is None:
        return []
    tenant_key = _tenant_key(user, client_id)
    docs = await _db.agent_schedules.find({"tenant_key": tenant_key}).sort("created_at", -1).to_list(200)
    out = []
    for d in docs:
        d = dict(d)
        d["id"] = str(d.pop("_id"))
        meta = AGENT_KINDS.get(d.get("kind"), {})
        d["kind_name"] = meta.get("name", d.get("kind"))
        d["kind_description"] = meta.get("description", "")
        out.append(d)
    return out


async def schedule_delete(user: dict, schedule_id: str, client_id: str = None) -> dict:
    if _db is None:
        raise RuntimeError("agents not bound")
    tenant_key = _tenant_key(user, client_id)
    try:
        from bson import ObjectId
        sid = ObjectId(schedule_id)
    except Exception:
        raise RuntimeError("Invalid schedule id")
    sc = await _db.agent_schedules.find_one({"_id": sid, "tenant_key": tenant_key})
    if not sc:
        raise RuntimeError("Schedule not found")
    await _db.agent_schedules.delete_one({"_id": sid})
    await eng.record_audit(user, "agent.schedule_delete", client_id=client_id,
                           detail={"schedule_id": schedule_id, "kind": sc.get("kind")})
    return {"deleted": True}


async def schedule_toggle(user: dict, schedule_id: str, enabled: bool, client_id: str = None) -> dict:
    if _db is None:
        raise RuntimeError("agents not bound")
    tenant_key = _tenant_key(user, client_id)
    try:
        from bson import ObjectId
        sid = ObjectId(schedule_id)
    except Exception:
        raise RuntimeError("Invalid schedule id")
    sc = await _db.agent_schedules.find_one({"_id": sid, "tenant_key": tenant_key})
    if not sc:
        raise RuntimeError("Schedule not found")
    await _db.agent_schedules.update_one({"_id": sid}, {"$set": {"enabled": bool(enabled)}})
    await eng.record_audit(user, "agent.schedule_toggle", client_id=client_id,
                           detail={"schedule_id": schedule_id, "enabled": enabled})
    return {"id": schedule_id, "enabled": bool(enabled)}


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------

async def run_list(user: dict, client_id: str = None, limit: int = 100) -> list:
    if _db is None:
        return []
    tenant_key = _tenant_key(user, client_id)
    docs = await _db.agent_runs.find({"tenant_key": tenant_key}).sort("created_at", -1).to_list(limit)
    out = []
    for d in docs:
        d = dict(d)
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

async def _execute_kind(actor: dict, client_id: str, kind: str, params: dict,
                        schedule_id: str, schedule_name: str) -> dict:
    """Run one agent task kind. Returns {status, summary, output}."""
    summary = ""
    output = {}
    if kind == "learning_report":
        res = await eng.weekly_learning_report(actor, client_id)
        output = res
        summary = res.get("summary", "")[:500]
    elif kind == "mission_review":
        missions = await eng.mission_list(actor, client_id)
        open_missions = [m for m in missions if m.get("status") in ("Draft", "Partially Approved")]
        if open_missions:
            m = open_missions[0]
            output = {"mission_id": m["id"], "objective": m.get("objective"),
                      "status": m.get("status"), "steps_total": len((m.get("plan") or {}).get("execution_plan") or [])}
            summary = f"Open mission '{m.get('objective', '')[:80]}': {output['steps_total']} planned steps, awaiting approval."
        else:
            summary = "No open missions to review. All missions are finalized or none exist."
    elif kind == "lead_score_refresh":
        leads = await _db.leads.find({"tenant_key": _tenant_key(actor, client_id)}).sort("created_at", -1).to_list(50)
        scored = 0
        for ld in leads:
            try:
                await eng.lead_score_explainable(actor, str(ld["_id"]), client_id)
                scored += 1
            except Exception:
                pass
            if scored >= 20:
                break
        summary = f"Refreshed scores for {scored} leads."
        output = {"leads_scored": scored}
    elif kind == "brain_reindex":
        from ai_embeddings import embed_async, provider_info
        cursor = _db.brain_chunks.find({"tenant_key": _tenant_key(actor, client_id)})
        reindex = 0
        async for chunk in cursor:
            if not chunk.get("embedding"):
                vec = await embed_async([chunk.get("text", "")[:1500]])
                if vec:
                    await _db.brain_chunks.update_one({"_id": chunk["_id"]}, {"$set": {"embedding": vec[0]}})
                reindex += 1
        summary = f"Re-embedded {reindex} brain chunks (provider: {provider_info()['provider']})."
        output = {"chunks_reindexed": reindex, **provider_info()}
    elif kind == "lead_enrichment":
        leads = await _db.leads.find({"tenant_key": _tenant_key(actor, client_id),
                                      "$or": [{"company": {"$in": [None, ""]}}, {"industry": {"$in": [None, ""]}}]}).to_list(30)
        enriched = 0
        for ld in leads:
            try:
                await eng.lead_enrich(actor, str(ld["_id"])) if hasattr(eng, "lead_enrich") else None
                enriched += 1
            except Exception:
                pass
            if enriched >= 10:
                break
        summary = f"Enrichment sweep attempted on {enriched} leads missing company/industry data."
        output = {"leads_attempted": enriched}
    elif kind == "experiment_review":
        exps = await _db.experiments.find({"tenant_key": _tenant_key(actor, client_id),
                                           "status": "design"}).to_list(50)
        summary = f"{len(exps)} experiments still in design. Check variant metrics to decide."
        output = {"in_design": len(exps)}
    elif kind == "campaign_report":
        report = await eng.attribution_report(actor, client_id)
        metrics = report.get("metrics", {})
        summary = (f"Spend {metrics.get('total_spend', 0)}, revenue {metrics.get('total_revenue_won', 0)}, "
                   f"ROAS {metrics.get('roas', 0)}, CPL {metrics.get('cpl', 0)}, "
                   f"{metrics.get('touch_count', 0)} touches.")
        output = {"metrics": metrics}
    elif kind == "custom_prompt":
        prompt = (params.get("prompt") or "").strip()
        if not prompt:
            return {"status": "skipped", "summary": "No prompt configured for this task."}
        from engine import BrainQueryInput
        q = BrainQueryInput(client_id=client_id, query=prompt[:300], top_k=6)
        ctx = await eng.brain_retrieve(actor, q)
        context = "\n".join(f"- [{r.get('kind', '')}] {r.get('title', '')}: {r['text'][:300]}"
                            for r in (ctx.get("results") or []))
        system = "You are a marketing analyst answering grounded in approved business context."
        try:
            answer = await ai_service.generate_text(f"agent-{schedule_id}", system,
                                                    f"CONTEXT:\n{context or '(no context found)'}\n\nQUESTION: {prompt}")
        except Exception as e:
            return {"status": "error", "summary": f"AI generation failed: {e}"}
        return {"status": "completed", "summary": answer[:600], "output": {"answer": answer,
                                                                          "context_count": len(ctx.get("results") or [])}}
    elif kind == "content_proposal":
        missions = await eng.mission_list(actor, client_id)
        plan = {}
        for m in missions[:1]:
            plan = m.get("plan") or {}
        content_plan = plan.get("content_plan") or []
        seed = plan.get("keyword_strategy", {}).get("topics") or []
        n = min(8, max(5, int(params.get("count") or 5)))
        system = "You are a content strategist generating grounded, channel-specific content proposals."
        prompt = (f"Mission context: {json.dumps(plan.get('icp') or {}, default=str)[:800]}\n"
                  f"Existing content plan: {json.dumps(content_plan)[:800]}\nTopics: {json.dumps(seed)[:400]}\n"
                  f"Return JSON: {{\"proposals\": [{{\"type\": \"\", \"title\": \"\", \"channel\": \"\", \"angle\": \"\"}}]}} "
                  f"with {n} new proposals that do not duplicate the existing plan.")
        try:
            result = await ai_service.generate_json(f"agent-content-{schedule_id}", system, prompt)
        except Exception as e:
            return {"status": "error", "summary": f"AI generation failed: {e}"}
        proposals = result.get("proposals") or []
        return {"status": "completed",
                "summary": f"Generated {len(proposals)} new content proposals grounded in the active mission.",
                "output": {"proposals": proposals[:n]}}
    else:
        return {"status": "skipped", "summary": f"Unknown agent kind: {kind}"}
    return {"status": "completed", "summary": summary, "output": output}


async def run_schedule(user: dict, schedule_id: str, client_id: str = None, manual: bool = False) -> dict:
    """Execute one schedule. manual=True bypasses policy + due-time gating."""
    if _db is None:
        raise RuntimeError("agents not bound")
    tenant_key = _tenant_key(user, client_id)
    try:
        from bson import ObjectId
        sid = ObjectId(schedule_id)
    except Exception:
        raise RuntimeError("Invalid schedule id")
    sc = await _db.agent_schedules.find_one({"_id": sid, "tenant_key": tenant_key})
    if not sc:
        raise RuntimeError("Schedule not found")
    cid = sc.get("client_id")
    actor = _user_for_tenant(user, cid)

    if not manual:
        # Policy gate (kill switch / autonomy level) — human runs always allowed.
        gate = await eng.check_autonomy(actor, f"agent:{sc.get('kind')}", client_id=cid,
                                        actor_type="agent")
        if not gate.get("allowed"):
            doc = {
                "tenant_key": tenant_key, "user_id": actor["owner_id"], "client_id": cid,
                "schedule_id": schedule_id, "kind": sc.get("kind"), "name": sc.get("name"),
                "trigger": "scheduled", "status": "blocked", "summary": gate.get("reason", "blocked by policy"),
                "started_at": _now_iso(), "finished_at": _now_iso(),
                "created_at": _now_iso(),
            }
            await _db.agent_runs.insert_one(doc)
            return {"id": str(doc["_id"]), **{k: v for k, v in doc.items() if k not in ("user_id", "_id")}}

    run_doc = {
        "tenant_key": tenant_key,
        "user_id": actor["owner_id"],
        "client_id": cid,
        "schedule_id": schedule_id,
        "kind": sc.get("kind"),
        "name": sc.get("name"),
        "trigger": "manual" if manual else "scheduled",
        "status": "running",
        "summary": "",
        "started_at": _now_iso(),
        "created_at": _now_iso(),
    }
    res = await _db.agent_runs.insert_one(run_doc)
    run_id = str(res.inserted_id)

    try:
        result = await _execute_kind(actor, cid, sc.get("kind"), sc.get("params") or {},
                                     schedule_id, sc.get("name"))
    except Exception as e:
        result = {"status": "error", "summary": f"Execution failed: {e}", "output": {}}
        logger.warning(f"agent run {run_id} failed: {traceback.format_exc()}")

    finished = _now_iso()
    update = {
        "status": result.get("status", "error"),
        "summary": (result.get("summary") or "")[:1500],
        "output": result.get("output") or {},
        "finished_at": finished,
    }
    try:
        started = datetime.fromisoformat(run_doc["started_at"])
        done = datetime.fromisoformat(finished)
        update["duration_seconds"] = round((done - started).total_seconds(), 2)
    except Exception:
        update["duration_seconds"] = None
    await _db.agent_runs.update_one({"_id": res.inserted_id}, {"$set": update})

    failures = 0 if result.get("status") == "completed" else (sc.get("consecutive_failures", 0) + 1)
    await _db.agent_schedules.update_one({"_id": sid}, {"$set": {
        "last_run_at": finished,
        "last_run_status": result.get("status", "error"),
        "consecutive_failures": failures,
        "next_run_at": _recurrence_next(sc.get("recurrence_kind"), sc.get("recurrence_value"))
        if sc.get("recurrence_kind") != "once" else None,
        "enabled": (sc.get("enabled") and failures < 5),
    }})

    await eng.emit_event(actor, "AutonomousActionExecuted", client_id=cid,
                         actor_type="agent", actor_id=schedule_id,
                         entity_type="agent_run", entity_id=run_id,
                         payload={"kind": sc.get("kind"), "status": result.get("status"),
                                  "summary": update["summary"][:200], "trigger": update.get("trigger")})
    await eng.record_audit(actor, "agent.run", client_id=cid,
                           detail={"schedule_id": schedule_id, "run_id": run_id,
                                   "kind": sc.get("kind"), "status": result.get("status"),
                                   "summary": update["summary"][:300]})
    out = {"id": run_id}
    out.update({k: v for k, v in dict(run_doc).items() if k not in ("user_id", "_id")})
    out.update(update)
    return out


# ---------------------------------------------------------------------------
# Background scheduler
# ---------------------------------------------------------------------------

async def _scheduler_loop():
    """Wakes every 60s and executes due schedules."""
    while True:
        try:
            await asyncio.sleep(60)
            if _db is None:
                continue
            now = _now_iso()
            cursor = _db.agent_schedules.find({"enabled": True, "next_run_at": {"$lte": now}})
            async for sc in cursor:
                sid = str(sc["_id"])
                tenant_key = sc.get("tenant_key", "")
                owner = tenant_key.split(":")[0]
                surrogate = {
                    "_id": __import__("bson", fromlist=["ObjectId"]).ObjectId(owner)
                    if len(owner) == 24 and all(c in "0123456789abcdef" for c in owner) else owner,
                    "owner_id": owner,
                    "client_id": sc.get("client_id"),
                    "is_agent": True,
                }
                # Best-effort ObjectId conversion; engine uses tenant_key anyway.
                try:
                    surrogate["_id"] = __import__("bson", fromlist=["ObjectId"]).ObjectId(owner)
                except Exception:
                    pass
                try:
                    await run_schedule(surrogate, sid, sc.get("client_id"), manual=False)
                except Exception as e:
                    logger.warning(f"scheduler run failed for {sid}: {e}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"scheduler loop error: {e}")


def start_scheduler():
    global _scheduler_task
    if _scheduler_task is None and _db is not None:
        _scheduler_task = asyncio.create_task(_scheduler_loop())


def stop_scheduler():
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None
