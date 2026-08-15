"""Closed-loop revenue marketing engine core.

Implements the gap-bridge modules as service functions callable from server.py:
- event_store: append-only telemetry with deduplication keys (Section 24)
- brain: tenant-specific Business Brain with crawl ingest, chunking,
  keyword-based retrieval with metadata and source attribution (Module A)
- missions: goal-driven Marketing Mission planner (Module B)
- intel_extra: explainable lead scoring with intent signals (Module I)
- experiments: hypothesis-based experiments with decision rules (Module M)
- attribution: first/last/multi-touch attribution and revenue metrics (Module L)
- policy: autonomy policy enforcement and immutable audit log (Module Q)
- learning: weekly learning records fed back to planning (Module O)

Persistence uses the existing AsyncIOMotorClient database object; this module
is database-agnostic until bind_db() is called during app lifespan.
"""

import os
import re
import json
import math
import hashlib
import logging
from datetime import datetime, timezone, timedelta

import ai as ai_service
from engine_models import (
    BrainIngestInput, BrainQueryInput, MissionInput, ExperimentInput,
    ExperimentDecisionInput, AttributionTouchInput, RevenueEventInput,
    PolicyInput, MarketingEventInput, LeadIntentInput,
)

logger = logging.getLogger(__name__)

_db = None
_collection_lock = {}

CORE_EVENT_TYPES = {
    "MissionCreated", "MissionPlanApproved", "MissionPlanRejected",
    "AssetCreated", "AssetPublished", "CampaignCreated", "CampaignUpdated",
    "AdImpression", "AdClick", "WebsiteVisit", "CTAInteraction", "FormSubmitted",
    "LeadCreated", "LeadEnriched", "LeadVerified", "LeadScored",
    "OutreachSent", "ReplyReceived", "MeetingBooked", "MQLCreated", "SQLCreated",
    "OpportunityCreated", "OpportunityWon", "OpportunityLost",
    "RevenueRecorded", "ExperimentStarted", "ExperimentVariantActivated",
    "ExperimentDecision", "BudgetChanged", "AutonomousActionExecuted",
    "PolicyChanged", "KillSwitchActivated", "KillSwitchDeactivated",
    "LearningRecorded", "BrainIngested", "BrainSourceRemoved",
    "LeadDeduplicated", "LeadRejected", "ApprovalRequested", "ApprovalGranted",
}

AUTONOMY_LEVELS = ["suggest", "draft", "approve", "controlled_autopilot", "full_autopilot"]


def bind_db(database):
    global _db
    _db = database


def _ensure_indexes():
    if _db is None:
        return

    async def _create():
        try:
            await _db.marketing_events.create_index([("tenant_key", 1), ("correlation_id", 1)], unique=True)
            await _db.marketing_events.create_index("event_type")
            await _db.marketing_events.create_index("created_at")
            await _db.brain_chunks.create_index("tenant_key")
            await _db.brain_chunks.create_index("keywords")
            await _db.brain_sources.create_index("tenant_key")
            await _db.missions.create_index("tenant_key")
            await _db.leads.create_index("tenant_key")
            await _db.intent_signals.create_index("tenant_key")
            await _db.experiments.create_index("tenant_key")
            await _db.experiment_variants.create_index("experiment_id")
            await _db.attribution_touches.create_index("tenant_key")
            await _db.revenue_events.create_index("tenant_key")
            await _db.policies.create_index("tenant_key")
            await _db.audit_log.create_index("tenant_key")
            await _db.learning_records.create_index("tenant_key")
        except Exception as e:
            logger.warning(f"engine index creation failed: {e}")
    return _create()


# ---------------------------------------------------------------------------
# Append-only event store (telemetry)
# ---------------------------------------------------------------------------

def _tenant_key(user: dict, client_id: str = None) -> str:
    owner = user.get("owner_id") or str(user["_id"])
    cid = client_id if client_id else user.get("client_id")
    return f"{owner}:{cid}" if cid else owner


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe_key(event_type: str, tenant_key: str, correlation_id: str = None, payload: dict = None) -> str:
    seed = f"{event_type}|{tenant_key}|{correlation_id or ''}|{json.dumps(payload or {}, sort_keys=True)}"
    return hashlib.sha256(seed.encode()).hexdigest()


async def emit_event(user: dict, event_type: str, *, client_id: str = None, actor_type: str = "human",
                     actor_id: str = None, correlation_id: str = None, entity_type: str = None,
                     entity_id: str = None, payload: dict = None, dedupe: bool = True):
    """Append one telemetry event. Returns the id or None when deduplicated."""
    if _db is None:
        return None
    tenant_key = _tenant_key(user, client_id)
    if not correlation_id:
        correlation_id = _dedupe_key(event_type, tenant_key, payload=payload)[:32]
    doc = {
        "tenant_key": tenant_key,
        "event_type": event_type,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "correlation_id": correlation_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload or {},
        "created_at": _now_iso(),
    }
    try:
        if dedupe:
            res = await _db.marketing_events.update_one(
                {"tenant_key": tenant_key, "correlation_id": correlation_id},
                {"$setOnInsert": doc}, upsert=True)
            return str(res.upserted_id) if res.upserted_id else None
        res = await _db.marketing_events.insert_one(doc)
        return str(res.inserted_id)
    except Exception as e:
        logger.warning(f"event emit failed ({event_type}): {e}")
        return None


async def record_audit(user: dict, action: str, *, client_id: str = None, detail: dict = None,
                       actor_type: str = "human"):
    """Immutable audit entry for governance (Section FR-Q07)."""
    if _db is None:
        return None
    tenant_key = _tenant_key(user, client_id)
    doc = {
        "tenant_key": tenant_key,
        "actor_type": actor_type,
        "actor_id": str(user["_id"]),
        "action": action,
        "detail": detail or {},
        "created_at": _now_iso(),
    }
    try:
        res = await _db.audit_log.insert_one(doc)
        return str(res.inserted_id)
    except Exception as e:
        logger.warning(f"audit record failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Module A — Business Brain (ingest + keyword retrieval without paid embeddings)
# ---------------------------------------------------------------------------

_STOPWORDS = set((
    "a an the and or but of to in on at for with by from is are was were be been "
    "being it its this that these those as into via per its their ours yours our "
    "your we us they them he she you i me him her have has had do does did will "
    "would could should may might can shall not no nor so if then than too very "
    "about over under up down out off more most less least all each every some any "
    "only also just even still yet already now here there when where what which who "
    "whom why how whose whom among between through during before after above below"
).split())

_MARKETING_KEYWORDS = set((
    "software saas platform service product agency marketing sales lead leadgen "
    "pricing plan plans feature features enterprise small business solution "
    "solutioning ai artificial intelligence automation dashboard analytics report "
    "consulting coaching course training ebook webinar demo free trial support "
    "roi revenue growth pipeline campaign seo sem ads advertising email social "
    "content brand branding design development app website ecommerce shop store "
    "customer clients clients service services team experts founder ceo cto "
    "technology technologies api integration crm funnel conversion landing page "
    "roi cac cpl roas mql sql booking demo trial testimonial case study faq "
    "contact phone location address office remote global worldwide digital "
    "b2b b2c startup startups agency agencies expert experts specialist "
    "healthcare finance fintech legal education edtech ecommerce retail "
    "manufacturing logistics real estate insurance healthcare health wellness "
    "fitness food restaurant hospitality travel tourism construction engineering"
).split())


def _chunk_text(text: str, size: int = 600, overlap: int = 100) -> list:
    """Split text into overlapping chunks by paragraph/line boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text or "") if p.strip()]
    chunks, buf = [], ""
    for p in paragraphs:
        if len(buf) + len(p) > size and buf:
            chunks.append(buf)
            buf = buf[-overlap:] + (" " if buf.endswith((" ",)) else " ") + p
        else:
            buf = (buf + " " + p).strip()
    if buf:
        chunks.append(buf)
    if not chunks and text:
        words = text.split()
        for i in range(0, len(words), size - overlap):
            chunks.append(" ".join(words[i:i + size]))
    return chunks[:200]


def _extract_keywords(text: str) -> list:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9'.&+%-]{1,}", text.lower())
    freq = {}
    for i, t in enumerate(tokens):
        if t in _STOPWORDS or len(t) < 3 or not re.search(r"[a-z]", t):
            continue
        bigram = f"{tokens[i-1]} {t}" if i > 0 and tokens[i-1] not in _STOPWORDS else None
        for cand in (bigram, t):
            if cand:
                freq[cand] = freq.get(cand, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: -kv[1])
    kw = [k for k, _ in ranked[:20]]
    kw += [m for m in _MARKETING_KEYWORDS if m in text.lower()][:5]
    return list(dict.fromkeys(kw))[:25]


def _score_chunk(query_keywords: list, keywords: list, text: str) -> float:
    if not query_keywords:
        return 0.0
    ql = [q.lower() for q in query_keywords]
    text_lower = text.lower()
    exact = sum(1 for k in ql if any(k == w or k in w or w in k for w in keywords))
    contains = sum(1 for q in ql if q.lower() in text_lower)
    return (2.0 * exact + contains) / max(len(ql), 1)


async def brain_ingest(user: dict, data: BrainIngestInput) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    tenant_key = _tenant_key(user, data.client_id)
    title = (data.title or data.url or "Document").strip()
    content = (data.content or "").strip()
    source_type = data.kind or "webpage"

    if data.url and not content:
        try:
            import urllib.request
            req = urllib.request.Request(
                data.url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AIMarketBrain/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=25) as r:
                html = r.read().decode("utf-8", "ignore")
            text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            content = text[:30000]
            title = title if title != data.url else (data.url.split("//")[-1].split("/")[0] or data.url)
        except Exception as e:
            logger.warning(f"brain crawl failed for {data.url}: {e}")
            raise RuntimeError(f"Could not fetch {data.url}: {e}")

    if not content:
        raise RuntimeError("No content to ingest — provide a URL or pasted content.")

    chunks = _chunk_text(content)
    if not chunks:
        raise RuntimeError("Content produced no usable chunks.")

    removed = 0
    if source_type == "webpage" and data.url:
        res = await _db.brain_sources.delete_many({"tenant_key": tenant_key, "url": data.url})
        removed = res.deleted_count

    source_doc = {
        "tenant_key": tenant_key,
        "url": data.url,
        "title": title,
        "kind": source_type,
        "char_count": len(content),
        "chunk_count": len(chunks),
        "ingested_at": _now_iso(),
    }
    src_res = await _db.brain_sources.insert_one(source_doc)

    inserted = 0
    for idx, chunk in enumerate(chunks):
        kw = _extract_keywords(chunk)
        await _db.brain_chunks.insert_one({
            "tenant_key": tenant_key,
            "source_id": str(src_res.inserted_id),
            "url": data.url,
            "title": title,
            "kind": source_type,
            "chunk_index": idx,
            "text": chunk,
            "keywords": kw,
            "created_at": _now_iso(),
        })
        inserted += 1

    await emit_event(user, "BrainIngested", client_id=data.client_id,
                     payload={"title": title, "kind": source_type, "chunks": inserted, "removed": removed})
    await record_audit(user, "brain.ingest", client_id=data.client_id,
                       detail={"title": title, "kind": source_type, "chunks": inserted, "removed": removed})
    return {"title": title, "chunks": inserted, "removed": removed,
            "source_id": str(src_res.inserted_id),
            "message": f"Brain updated: {inserted} chunks from {title}"}


async def brain_sources(user: dict, client_id: str = None) -> list:
    if _db is None:
        return []
    tenant_key = _tenant_key(user, client_id)
    docs = await _db.brain_sources.find({"tenant_key": tenant_key}).sort("ingested_at", -1).to_list(100)
    out = []
    for d in docs:
        d = dict(d)
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out


async def brain_remove_source(user: dict, source_id: str, client_id: str = None) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    tenant_key = _tenant_key(user, client_id)
    try:
        sid = __import__("bson", fromlist=["ObjectId"]).ObjectId(source_id)
    except Exception:
        raise RuntimeError("Invalid source id")
    src = await _db.brain_sources.find_one({"_id": sid, "tenant_key": tenant_key})
    if not src:
        raise RuntimeError("Source not found")
    await _db.brain_chunks.delete_many({"tenant_key": tenant_key, "source_id": source_id})
    await _db.brain_sources.delete_one({"_id": sid})
    await emit_event(user, "BrainSourceRemoved", client_id=client_id,
                     payload={"title": src.get("title")})
    await record_audit(user, "brain.remove_source", client_id=client_id,
                       detail={"source_id": source_id, "title": src.get("title")})
    return {"removed": True, "title": src.get("title")}


async def brain_retrieve(user: dict, data: BrainQueryInput) -> dict:
    if _db is None:
        return {"results": []}
    tenant_key = _tenant_key(user, data.client_id)
    q_words = [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9'.&+%-]{1,}", data.query) if len(w) > 2]
    q_words = [w for w in q_words if w.lower() not in _STOPWORDS]
    cursor = _db.brain_chunks.find({"tenant_key": tenant_key})
    results = []
    seen = set()
    async for chunk in cursor:
        score = _score_chunk(q_words, chunk.get("keywords", []) or [], chunk.get("text", ""))
        if score <= 0:
            continue
        sig = (chunk.get("source_id"), chunk.get("chunk_index"))
        if sig in seen:
            continue
        seen.add(sig)
        results.append({
            "text": chunk.get("text", "")[:1400],
            "title": chunk.get("title"),
            "url": chunk.get("url"),
            "kind": chunk.get("kind"),
            "score": round(score, 3),
        })
    results.sort(key=lambda r: -r["score"])
    results = results[: data.top_k or 5]
    return {"query": data.query, "context_terms": q_words[:15], "results": results,
            "message": "Retrieved business context with source attribution."}


def _context_block_for(user_ctx: dict) -> str:
    """Build a compact context block for AI prompts from the brain (used by missions/scoring)."""
    # Accepts {"user": dict, "client_id": str|None} in user_ctx
    return ""   # lazy retrieval is done inline where needed


# ---------------------------------------------------------------------------
# Module B — Marketing Mission Planner
# ---------------------------------------------------------------------------

async def _retrieve_context(user: dict, client_id: str) -> str:
    try:
        q = BrainQueryInput(client_id=client_id, query="business products offer audience pricing claims", top_k=4)
        ctx = await brain_retrieve(user, q)
        parts = [f"- [{r['kind']}] {r['title']}: {r['text'][:400]}" for r in ctx.get("results", []) if r.get("text")]
        return "\n".join(parts) if parts else ""
    except Exception as e:
        logger.warning(f"context retrieval failed: {e}")
        return ""


async def mission_create(user: dict, data: MissionInput) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    tenant_key = _tenant_key(user, data.client_id)
    cid = data.client_id or user.get("client_id")

    profile = await _db.profiles.find_one({"user_id": tenant_key.split(":")[0], "client_id": cid}) or {}
    offer = data.offer or profile.get("description", "")
    market = data.target_market or profile.get("industry", "")
    geography = data.geography or profile.get("country", "")
    currency = data.currency or profile.get("currency", "USD")
    budget = data.budget if data.budget is not None else None
    website = profile.get("website", "")

    objective = data.objective.strip()
    if len(objective) < 10:
        raise RuntimeError("Objective is too short. Describe your goal, target market and offer.")

    context = await _retrieve_context(user, cid)
    context_note = f"APPROVED BUSINESS CONTEXT (use these facts, do not invent):\n{context}\n" if context else ""

    system = (
        "You are an autonomous Chief Marketing Officer. You convert a business goal into a complete, "
        "executable multi-channel marketing mission plan. Plans must prioritize qualified pipeline and "
        "revenue over vanity metrics, respect the autonomy level and any constraints, and be grounded in "
        "the approved business context."
    )
    prompt = f"""{context_note}
BUSINESS GOAL: {objective}
Target market: {market or 'auto-determine from context'}
Offer: {offer or 'auto-determine from context'}
Geography: {geography or 'auto-determine from context'}
Website: {website or 'not provided'}
Budget: {budget if budget is not None else 'not provided'}
Timeline: {data.timeline or 'auto-determine (default 90 days)'}
Constraints: {data.constraints or 'none'}
Currency: {currency}

Return JSON with EXACTLY this shape:
{{
  "mission_summary": "1-2 sentence restatement of the goal",
  "icp": {{"title": "", "company_profile": "", "decision_maker": "", "pain_points": ["", ""], "buying_triggers": ["", ""]}},
  "personas": [{{"name": "", "role": "", "motivations": "", "channels": ""}}],
  "channel_mix": [{{"channel": "", "allocation_pct": 25, "rationale": ""}}],
  "offer_strategy": "positioning + hook + proof approach",
  "keyword_strategy": {{"seed_terms": ["", ""], "topics": ["", ""]}},
  "content_plan": [{{"type": "blog|social|email|video|ad", "title": "", "purpose": ""}}],
  "lead_plan": "how leads are captured, verified and qualified",
  "conversion_plan": "nurture sequence and meeting booking approach",
  "measurement_plan": [{{"metric": "", "target": "", "period": ""}}],
  "forecast": {{"expected_leads_range": [0, 0], "expected_qualified_range": [0, 0], "assumptions": "", "confidence": "low|medium|high"}},
  "execution_plan": [{{"step": 1, "action": "", "channel": "", "owner": "agent|human", "day_range": "1-14"}}],
  "risks": ["", ""]
}}
channel_mix allocation_pct MUST sum to 100. execution_plan needs 4-8 steps."""

    result = await ai_service.generate_json(f"mission-{user['_id']}", system, prompt)

    plan_doc = {
        "tenant_key": tenant_key,
        "user_id": tenant_key.split(":")[0],
        "client_id": cid,
        "objective": objective,
        "input": data.model_dump(exclude_none=True),
        "plan": result,
        "status": "Draft",
        "approval_mode": "plan",            # approve whole plan or per-action
        "created_at": _now_iso(),
    }
    res = await _db.missions.insert_one(plan_doc)

    await emit_event(user, "MissionCreated", client_id=cid,
                     correlation_id=str(res.inserted_id)[:32],
                     entity_type="mission", entity_id=str(res.inserted_id),
                     payload={"objective": objective})
    await record_audit(user, "mission.create", client_id=cid,
                       detail={"objective": objective, "mission_id": str(res.inserted_id)})
    return {"id": str(res.inserted_id), "objective": objective, "plan": result, "status": "Draft"}


async def mission_approve(user: dict, mission_id: str, approve: bool,
                          action_index: int = None, edits: dict = None, client_id: str = None) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    tenant_key = _tenant_key(user, client_id)
    try:
        mid = __import__("bson", fromlist=["ObjectId"]).ObjectId(mission_id)
    except Exception:
        raise RuntimeError("Invalid mission id")
    m = await _db.missions.find_one({"_id": mid, "tenant_key": tenant_key})
    if not m:
        raise RuntimeError("Mission not found")
    if m.get("status") not in ("Draft", "Partially Approved"):
        raise RuntimeError("Mission already finalized")

    plan = dict(m.get("plan") or {})
    if edits and isinstance(edits, dict):
        plan.update(edits)

    if action_index is not None:
        steps = plan.get("execution_plan") or []
        if 0 <= action_index < len(steps):
            steps[action_index]["approved"] = bool(approve)
        status = "Partially Approved"
        approved_count = sum(1 for s in steps if s.get("approved"))
        msg = f"{approved_count}/{len(steps)} actions approved" if approve else "Action reverted"
        await emit_event(user, "ApprovalRequested" if approve else "ApprovalRequested",
                         client_id=client_id, actor_type="human",
                         entity_type="mission", entity_id=mission_id,
                         payload={"action_index": action_index, "approved": approve})
    else:
        status = "Approved" if approve else "Rejected"
        for s in (plan.get("execution_plan") or []):
            s["approved"] = bool(approve)
        msg = "Mission plan approved — launch enabled" if approve else "Mission plan rejected"
        await emit_event(user, "MissionPlanApproved" if approve else "MissionPlanRejected",
                         client_id=client_id, actor_type="human",
                         entity_type="mission", entity_id=mission_id,
                         payload={"objective": m.get("objective")})
        await record_audit(user, "mission.approve" if approve else "mission.reject",
                           client_id=client_id, detail={"mission_id": mission_id})

    await _db.missions.update_one({"_id": mid}, {"$set": {"plan": plan, "status": status}})
    return {"id": mission_id, "status": status, "plan": plan, "message": msg}


async def mission_list(user: dict, client_id: str = None) -> list:
    if _db is None:
        return []
    tenant_key = _tenant_key(user, client_id)
    docs = await _db.missions.find({"tenant_key": tenant_key}).sort("created_at", -1).to_list(50)
    out = []
    for d in docs:
        d = dict(d)
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Module I — Explainable lead scoring with intent signals
# ---------------------------------------------------------------------------

def _grade_list(value: str, positive: list, negative: list = None) -> float:
    v = (value or "").lower()
    if not v:
        return 0.5
    pos = sum(1 for p in positive if p in v)
    neg = sum(1 for p in (negative or []) if p in v)
    return max(0.0, min(1.0, 0.5 + 0.18 * (pos - neg)))


async def lead_score_explainable(user: dict, lead_id: str, client_id: str = None) -> dict:
    """Compute ICP fit + behavior + intent + recency composite with reason codes."""
    if _db is None:
        raise RuntimeError("engine not bound")
    tenant_key = _tenant_key(user, client_id)
    try:
        lid = __import__("bson", fromlist=["ObjectId"]).ObjectId(lead_id)
    except Exception:
        raise RuntimeError("Invalid lead id")
    lead = await _db.leads.find_one({"_id": lid, "tenant_key": tenant_key})
    if not lead:
        lead = await _db.leads.find_one({"_id": lid, "user_id": tenant_key.split(":")[0]})
    if not lead:
        raise RuntimeError("Lead not found")

    profile = await _db.profiles.find_one({"user_id": lead.get("user_id"),
                                           "client_id": lead.get("client_id")}) or {}
    industry = (profile.get("industry") or "").lower()

    # Fit score: role seniority, company relevance, industry match, budget signal
    fit_factors = []
    role = (lead.get("role") or "").lower()
    senior = ["founder", "ceo", "cto", "cfo", "owner", "director", "head", "vp", "partner", "manager"]
    junior = ["intern", "assistant", "associate", "junior", "coordinator", "support"]
    role_score = 0.85 if any(s in role for s in senior) else (0.35 if any(j in role for j in junior) else 0.55)
    fit_factors.append(("Decision-maker role", role_score))
    ind_score = _grade_list(lead.get("industry", ""), [industry] if industry else [], [])
    fit_factors.append(("Industry match", ind_score))
    budget = (lead.get("budget") or "").lower()
    budget_score = 0.85 if any(b in budget for b in ["high", "large", "5k", "10k", "50k", "100k", "$"]) else 0.5
    fit_factors.append(("Budget signal", budget_score))
    company_score = _grade_list(lead.get("company", ""), [], ["gmail.com", "yahoo.com", "hotmail.com"])
    fit_factors.append(("Company quality", company_score))
    fit = round(sum(s for _, s in fit_factors) / len(fit_factors) * 100, 1)

    # Behavioral score from intent signals
    signals = await _db.intent_signals.find({"tenant_key": tenant_key, "lead_id": lead_id}).to_list(1000)
    if not signals:
        signals = await _db.intent_signals.find({"lead_id": lead_id}).to_list(1000)
    weights = {
        "reply": 1.0, "demo_request": 1.0, "meeting_booked": 1.0, "form_submitted": 0.85,
        "email_click": 0.7, "email_open": 0.4, "page_visit": 0.3, "social_engage": 0.35,
        "proposal_viewed": 0.6, "pricing_viewed": 0.75,
    }
    beh_total = 0.0
    seen_types = {}
    for s in signals:
        t = s.get("signal_type", "")
        w = float(s.get("weight") or weights.get(t, 0.2))
        beh_total += w
        seen_types[t] = max(seen_types.get(t, 0), w)
    behavior = round(min(100.0, beh_total * 20), 1)
    beh_factors = [(t.replace("_", " ").title(), min(100.0, w * 100)) for t, w in sorted(seen_types.items(), key=lambda kv: -kv[1])[:4]]

    # Recency score
    recency = 0.0
    if signals:
        last = max(s.get("created_at", "") for s in signals)
        try:
            dt = datetime.fromisoformat(last)
            days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
            recency = round(max(0, 100 - days * 3), 1)
        except Exception:
            recency = 20.0

    composite = round(0.45 * fit + 0.35 * behavior + 0.20 * recency, 1)
    if composite >= 75:
        category = "Hot"
    elif composite >= 55:
        category = "Warm"
    elif composite >= 35:
        category = "Cold"
    else:
        category = "Cold"

    reasons = [f"{name}: {round(s*100, 0):.0f}%" for name, s in fit_factors]
    if beh_factors:
        reasons += [f"behavior {n}: {round(v, 0):.0f}%" for n, v in beh_factors]
    reasons.append(f"recency: {recency:.0f}%")

    await _db.leads.update_one({"_id": lid}, {"$set": {
        "score": composite, "category": category,
        "reasoning": "; ".join(reasons),
        "scores": {"fit": fit, "behavior": behavior, "recency": recency,
                   "components": reasons},
    }})
    await emit_event(user, "LeadScored", client_id=client_id,
                     entity_type="lead", entity_id=lead_id,
                     payload={"score": composite, "category": category})
    lead = await _db.leads.find_one({"_id": lid})
    lead = dict(lead)
    lead["id"] = str(lead.pop("_id"))
    return lead


async def lead_add_intent(user: dict, data: LeadIntentInput) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    tenant_key = _tenant_key(user, data.lead_id and None)
    lead = await _db.leads.find_one({"_id": __import__("bson", fromlist=["ObjectId"]).ObjectId(data.lead_id)})
    if not lead:
        raise RuntimeError("Lead not found")
    doc = {
        "tenant_key": f"{lead.get('user_id')}:{lead.get('client_id')}" if lead.get("client_id") else str(lead.get("user_id")),
        "user_id": lead.get("user_id"),
        "client_id": lead.get("client_id"),
        "lead_id": data.lead_id,
        "signal_type": data.signal_type,
        "details": data.details or "",
        "weight": float(data.weight) if data.weight is not None else None,
        "created_at": _now_iso(),
    }
    await _db.intent_signals.insert_one(doc)
    await emit_event(user, data.signal_type.replace("_", " ").title().replace(" ", ""),
                     client_id=lead.get("client_id"), entity_type="lead",
                     entity_id=data.lead_id, payload={"signal_type": data.signal_type})
    return {"recorded": True, "signal": data.signal_type}


# ---------------------------------------------------------------------------
# Module M — Experiments
# ---------------------------------------------------------------------------

async def experiment_create(user: dict, data: ExperimentInput) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    if len(data.variants) < 2:
        raise RuntimeError("At least two variants are required for a valid experiment.")
    tenant_key = _tenant_key(user, data.client_id)
    doc = {
        "tenant_key": tenant_key,
        "user_id": tenant_key.split(":")[0],
        "client_id": data.client_id or user.get("client_id"),
        "name": data.name,
        "hypothesis": data.hypothesis,
        "variables": data.variables,
        "primary_metric": data.primary_metric,
        "guardrails": data.guardrails or "",
        "min_sample": max(10, int(data.min_sample or 100)),
        "status": "design",
        "created_at": _now_iso(),
    }
    res = await _db.experiments.insert_one(doc)
    exp_id = str(res.inserted_id)
    for v in data.variants:
        await _db.experiment_variants.insert_one({
            "experiment_id": exp_id,
            "tenant_key": tenant_key,
            "name": v.get("name", f"Variant {len(v)+1}"),
            "config": {k: val for k, val in v.items() if k != "name"},
            "status": "active",
            "impressions": 0, "clicks": 0, "conversions": 0,
            "revenue": 0.0,
            "created_at": _now_iso(),
        })
    await emit_event(user, "ExperimentStarted", client_id=data.client_id,
                     entity_type="experiment", entity_id=exp_id,
                     payload={"name": data.name, "variants": len(data.variants)})
    await record_audit(user, "experiment.create", client_id=data.client_id,
                       detail={"experiment_id": exp_id, "name": data.name})
    return {"id": exp_id, "message": "Experiment created with variants. Activate variants to begin."}


def _two_proportion_z(p1, n1, p2, n2):
    if n1 < 5 or n2 < 5:
        return None
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return None
    return abs(p1 - p2) / se


async def experiment_decide(user: dict, experiment_id: str, decision: ExperimentDecisionInput) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    try:
        eid = __import__("bson", fromlist=["ObjectId"]).ObjectId(experiment_id)
    except Exception:
        raise RuntimeError("Invalid experiment id")
    exp = await _db.experiments.find_one({"_id": eid})
    if not exp:
        raise RuntimeError("Experiment not found")

    variants = await _db.experiment_variants.find({"experiment_id": experiment_id}).to_list(20)
    total_metric = sum(v.get("conversions", 0) or 0 for v in variants)
    min_sample = exp.get("min_sample", 100)

    reasons = []
    if total_metric < min_sample:
        verdict = "needs_more_data"
        reasons.append(f"Total conversions {total_metric} below minimum sample {min_sample}. "
                       "Declaring a winner now risks a false conclusion.")
    else:
        verdict = decision.decision or "inconclusive"
        if len(variants) >= 2:
            a, b = variants[0], variants[1]
            ca, cb = a.get("conversions", 0) or 0, b.get("conversions", 0) or 0
            z = _two_proportion_z(ca / max(a.get("impressions", 1), 1), max(a.get("impressions", 1), 1),
                                  cb / max(b.get("impressions", 1), 1), max(b.get("impressions", 1), 1))
            if z is not None:
                reasons.append(f"Two-proportion z-statistic: {z:.2f} (|z|>1.96 ≈ 95% confidence)")
                if z > 1.96 and verdict != "winner":
                    verdict = "winner"
        if decision.variant_winner_id:
            reasons.append(f"Human-declared winner variant: {decision.variant_winner_id}")

    for v in variants:
        if decision.variant_winner_id and str(v["_id"]) == decision.variant_winner_id:
            await _db.experiment_variants.update_one({"_id": v["_id"]}, {"$set": {"status": "winner"}})
        elif verdict in ("winner", "loser"):
            await _db.experiment_variants.update_one({"_id": v["_id"]}, {"$set": {"status": "runner_up"}})

    await _db.experiments.update_one({"_id": eid}, {"$set": {"status": verdict, "verdict_reasons": reasons}})
    await emit_event(user, "ExperimentDecision", client_id=exp.get("client_id"),
                     entity_type="experiment", entity_id=experiment_id,
                     payload={"experiment": exp.get("name"), "verdict": verdict,
                              "total_metric": total_metric, "min_sample": min_sample})
    await record_audit(user, "experiment.decision", client_id=exp.get("client_id"),
                       detail={"experiment_id": experiment_id, "verdict": verdict, "reasons": reasons})

    if verdict == "winner":
        await _learning_record(user, exp.get("client_id"),
                               f"Experiment '{exp.get('name')}' declared a winner. " + "; ".join(reasons))

    return {"experiment_id": experiment_id, "verdict": verdict,
            "total_metric": total_metric, "min_sample": min_sample, "reasons": reasons}


# ---------------------------------------------------------------------------
# Module L — Attribution & revenue
# ---------------------------------------------------------------------------

async def attribution_touch(user: dict, data: AttributionTouchInput) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    lead = None
    if data.lead_id:
        try:
            lead = await _db.leads.find_one(
                {"_id": __import__("bson", fromlist=["ObjectId"]).ObjectId(data.lead_id)})
        except Exception:
            lead = None
    if not lead:
        raise RuntimeError("Lead not found")
    tenant_key = f"{lead.get('user_id')}:{lead.get('client_id')}" if lead.get("client_id") else str(lead.get("user_id"))
    doc = {
        "tenant_key": tenant_key,
        "lead_id": data.lead_id,
        "campaign_id": data.campaign_id,
        "channel": data.channel,
        "touch_type": data.touch_type,
        "details": data.details or "",
        "value": float(data.value) if data.value is not None else None,
        "created_at": _now_iso(),
    }
    await _db.attribution_touches.insert_one(doc)
    await emit_event(user, data.touch_type.title() + "Touch", client_id=data.client_id,
                     entity_type="lead", entity_id=data.lead_id,
                     payload={"channel": data.channel, "touch_type": data.touch_type})
    return {"recorded": True}


async def revenue_record(user: dict, data: RevenueEventInput) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    lead = None
    if data.lead_id:
        try:
            lead = await _db.leads.find_one(
                {"_id": __import__("bson", fromlist=["ObjectId"]).ObjectId(data.lead_id)})
        except Exception:
            lead = None
    if not lead:
        raise RuntimeError("Lead not found")
    tenant_key = f"{lead.get('user_id')}:{lead.get('client_id')}" if lead.get("client_id") else str(lead.get("user_id"))
    if data.stage == "won":
        await _db.leads.update_one({"_id": lead["_id"]}, {"$set": {"stage": "Won"}})
    doc = {
        "tenant_key": tenant_key,
        "lead_id": data.lead_id,
        "campaign_id": data.campaign_id,
        "amount": float(data.amount),
        "currency": data.currency or "USD",
        "stage": data.stage,
        "notes": data.notes or "",
        "created_at": _now_iso(),
    }
    await _db.revenue_events.insert_one(doc)
    await emit_event(user, "RevenueRecorded" if data.stage == "won" else "OpportunityCreated",
                     client_id=data.client_id, entity_type="lead", entity_id=data.lead_id,
                     payload={"amount": data.amount, "stage": data.stage})
    await record_audit(user, "revenue.record", client_id=data.client_id,
                       detail={"lead_id": data.lead_id, "amount": data.amount, "stage": data.stage})
    if data.stage == "won":
        await _learning_record(user, data.client_id,
                               f"Revenue recorded: {data.currency or 'USD'} {data.amount:.2f} "
                               f"from lead {lead.get('name')} ({lead.get('company')}).")
    return {"recorded": True, "amount": data.amount, "stage": data.stage}


async def revenue_list(user: dict, client_id: str = None) -> list:
    if _db is None:
        return []
    tenant_key = _tenant_key(user, client_id)
    docs = await _db.revenue_events.find({"tenant_key": tenant_key}).sort("created_at", -1).to_list(200)
    return [{**dict(d), "id": str(d.pop("_id"))} for d in docs]


async def attribution_report(user: dict, client_id: str = None) -> dict:
    if _db is None:
        return {"touches": [], "revenue": [], "metrics": {}}
    tenant_key = _tenant_key(user, client_id)
    uid = tenant_key.split(":")[0]
    base = {"tenant_key": tenant_key}

    touches = await _db.attribution_touches.find(base).sort("created_at", 1).to_list(5000)
    revenue = await _db.revenue_events.find(base).sort("created_at", -1).to_list(500)
    campaigns = await _db.campaigns.find({"user_id": uid, **({"client_id": client_id} if client_id else {})}).to_list(500)

    total_spend = sum(c.get("budget", 0) or 0 for c in campaigns)
    total_revenue = sum(r.get("amount", 0) or 0 for r in revenue if r.get("stage") == "won")
    revenue_by_channel = {}
    for t in touches:
        ch = t.get("channel", "Unknown")
        entry = revenue_by_channel.setdefault(ch, {"channel": ch, "touches": 0,
                                                   "first_touch": 0, "last_touch": 0, "multi": 0.0})
        entry["touches"] += 1
        if t.get("touch_type") == "first":
            entry["first_touch"] += 1
        elif t.get("touch_type") == "last":
            entry["last_touch"] += 1
        elif t.get("touch_type") == "interaction":
            entry["multi"] += 1
    for e in revenue_by_channel.values():
        e["first_touch_revenue"] = round(total_revenue * e["first_touch"] / max(sum(x["first_touch"] for x in revenue_by_channel.values()), 1), 2)

    cpl = round(total_spend / max(len(touches), 1), 2)
    cac = round(total_spend / max(len([r for r in revenue if r.get("stage") == "won"]), 1), 2)
    roas = round(total_revenue / total_spend, 2) if total_spend else 0

    return {
        "touches": [_serialize_touch(t) for t in touches[-50:]],
        "revenue": [_serialize_touch(r) for r in revenue[:50]],
        "metrics": {
            "total_spend": round(total_spend, 2),
            "total_revenue_won": round(total_revenue, 2),
            "roas": roas, "cpl": cpl, "cac": cac,
            "touch_count": len(touches),
            "revenue_event_count": len(revenue),
            "channel_attribution": list(revenue_by_channel.values()),
        },
    }


def _serialize_touch(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


# ---------------------------------------------------------------------------
# Module Q — Autonomy policy & governance
# ---------------------------------------------------------------------------

async def policy_set(user: dict, data: PolicyInput) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    level = data.autonomy_level
    if level not in AUTONOMY_LEVELS:
        raise RuntimeError(f"Autonomy level must be one of: {', '.join(AUTONOMY_LEVELS)}")
    tenant_key = _tenant_key(user, data.client_id)
    doc = {
        "tenant_key": tenant_key,
        "user_id": tenant_key.split(":")[0],
        "client_id": data.client_id or user.get("client_id"),
        "autonomy_level": level,
        "max_daily_spend": float(data.max_daily_spend) if data.max_daily_spend else None,
        "max_budget_change_pct": float(data.max_budget_change_pct) if data.max_budget_change_pct is not None else 25.0,
        "channels_allowed": data.channels_allowed,
        "countries_allowed": data.countries_allowed,
        "require_approval_over_amount": float(data.require_approval_over_amount) if data.require_approval_over_amount else None,
        "kill_switch": bool(data.kill_switch),
        "updated_at": _now_iso(),
    }
    await _db.policies.update_one({"tenant_key": tenant_key}, {"$set": doc}, upsert=True)
    await emit_event(user, "PolicyChanged", client_id=data.client_id,
                     payload={"autonomy_level": level, "kill_switch": doc["kill_switch"]})
    await record_audit(user, "policy.set", client_id=data.client_id,
                       detail={"autonomy_level": level, "kill_switch": doc["kill_switch"]})
    return doc


async def policy_get(user: dict, client_id: str = None) -> dict:
    if _db is None:
        return {"autonomy_level": "suggest", "kill_switch": False}
    tenant_key = _tenant_key(user, client_id)
    doc = await _db.policies.find_one({"tenant_key": tenant_key})
    if not doc:
        return {"autonomy_level": "suggest", "kill_switch": False,
                "max_daily_spend": None, "max_budget_change_pct": 25.0,
                "channels_allowed": None, "countries_allowed": None,
                "require_approval_over_amount": None}
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


async def kill_switch(user: dict, active: bool, client_id: str = None) -> dict:
    if _db is None:
        raise RuntimeError("engine not bound")
    tenant_key = _tenant_key(user, client_id)
    await _db.policies.update_one({"tenant_key": tenant_key},
                                  {"$set": {"kill_switch": bool(active), "updated_at": _now_iso()}}, upsert=True)
    await emit_event(user, "KillSwitchActivated" if active else "KillSwitchDeactivated",
                     client_id=client_id, payload={"active": active})
    await record_audit(user, "kill_switch", client_id=client_id,
                       detail={"active": active}, actor_type="human")
    return {"kill_switch": bool(active), "message": "All autonomous actions paused." if active else "Autonomy restored."}


async def check_autonomy(user: dict, action: str, *, client_id: str = None, amount: float = None,
                         channel: str = None, actor_type: str = "agent") -> dict:
    """Gate an autonomous action against policy. Returns allowed + reason."""
    policy = await policy_get(user, client_id)
    kill = policy.get("kill_switch")
    level = policy.get("autonomy_level", "suggest")
    if kill:
        return {"allowed": False, "reason": "Emergency kill switch is active. All autonomous actions are paused."}
    idx = AUTONOMY_LEVELS.index(level)
    if actor_type != "human" and idx == 0:
        return {"allowed": False, "reason": "Autonomy is in Suggest mode. Actions require human approval."}
    approval_level = AUTONOMY_LEVELS.index("approve")
    if actor_type != "human" and idx < approval_level and amount and policy.get("require_approval_over_amount"):
        if amount > policy["require_approval_over_amount"]:
            return {"allowed": False, "reason": f"Amount {amount} exceeds approval threshold "
                                                f"{policy['require_approval_over_amount']}."}
    if channel and policy.get("channels_allowed") and channel not in policy["channels_allowed"]:
        return {"allowed": False, "reason": f"Channel {channel} is not in the allowed channel list."}
    return {"allowed": True, "reason": "Within policy.", "autonomy_level": level}


# ---------------------------------------------------------------------------
# Module O — Revenue intelligence & learning
# ---------------------------------------------------------------------------

async def _learning_record(user: dict, client_id: str, finding: str,
                           confidence: str = "medium", next_actions: list = None):
    doc = {
        "tenant_key": _tenant_key(user, client_id),
        "user_id": _tenant_key(user, client_id).split(":")[0],
        "client_id": client_id or user.get("client_id"),
        "finding": finding,
        "confidence": confidence,
        "next_actions": next_actions or [],
        "created_at": _now_iso(),
    }
    try:
        await _db.learning_records.insert_one(doc)
    except Exception as e:
        logger.warning(f"learning record failed: {e}")


async def learning_records(user: dict, client_id: str = None, limit: int = 30) -> list:
    if _db is None:
        return []
    tenant_key = _tenant_key(user, client_id)
    docs = await _db.learning_records.find({"tenant_key": tenant_key}).sort("created_at", -1).to_list(limit)
    out = []
    for d in docs:
        d = dict(d)
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out


async def weekly_learning_report(user: dict, client_id: str = None) -> dict:
    """Generate a weekly learning record: winners, losers, reasons, next experiments."""
    if _db is None:
        raise RuntimeError("engine not bound")
    tenant_key = _tenant_key(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    exps = await _db.experiments.find({"tenant_key": tenant_key}).to_list(200)
    revenue = await _db.revenue_events.find({"tenant_key": tenant_key, "created_at": {"$gte": since}}).to_list(500)
    wins = [e for e in exps if e.get("status") == "winner" and e.get("created_at", "") >= since]
    losses = [e for e in exps if e.get("status") == "loser" and e.get("created_at", "") >= since]
    campaigns = await _db.campaigns.find({"user_id": tenant_key.split(":")[0]}).to_list(500)
    poor = [c for c in campaigns if (c.get("budget", 0) or 0) > 0 and
            ((c.get("revenue", 0) or 0) / max(c.get("budget", 1), 1)) < 0.5 and (c.get("conversions", 0) or 0) == 0]

    system = (
        "You are a revenue marketing analyst. Summarize last week's marketing outcomes into a concise "
        "learning record and propose the next experiments."
    )
    prompt = f"""Winning experiments this week: {json.dumps([{'name': w.get('name'), 'hypothesis': w.get('hypothesis')} for w in wins]) or 'none'}
Losing experiments: {json.dumps([{'name': l.get('name')} for l in losses]) or 'none'}
Underperforming campaigns (ROAS < 0.5, no conversions): {[c.get('name') for c in poor]} or none
Revenue recorded: {len(revenue)} events, total {sum(r.get('amount', 0) or 0 for r in revenue if r.get('stage') == 'won')}
Return JSON: {{"summary": "", "winners": [""], "losers": [""], "reasons": [""], "next_experiments": [""], "confidence": "low|medium|high"}}"""
    try:
        result = await ai_service.generate_json(f"weekly-learning-{user['_id']}", system, prompt)
    except Exception as e:
        logger.warning(f"weekly learning generation failed: {e}")
        result = {"summary": "Not enough activity this week to generate learnings.",
                  "winners": [], "losers": [], "reasons": [], "next_experiments": [], "confidence": "low"}

    doc = {
        "tenant_key": tenant_key,
        "user_id": tenant_key.split(":")[0],
        "client_id": client_id or user.get("client_id"),
        "period": "weekly",
        **result,
        "generated_at": _now_iso(),
    }
    res = await _db.learning_records.insert_one(doc)
    await emit_event(user, "LearningRecorded", client_id=client_id,
                     payload={"period": "weekly", "winners": len(result.get("winners", []))})
    return {"id": str(res.inserted_id), **result}


# ---------------------------------------------------------------------------
# Events feed
# ---------------------------------------------------------------------------

async def events_feed(user: dict, client_id: str = None, limit: int = 100, event_type: str = None) -> list:
    if _db is None:
        return []
    tenant_key = _tenant_key(user, client_id)
    q = {"tenant_key": tenant_key}
    if event_type:
        q["event_type"] = {"$regex": event_type, "$options": "i"}
    docs = await _db.marketing_events.find(q).sort("created_at", -1).to_list(limit)
    out = []
    for d in docs:
        d = dict(d)
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out


async def audit_feed(user: dict, client_id: str = None, limit: int = 200) -> list:
    if _db is None:
        return []
    tenant_key = _tenant_key(user, client_id)
    docs = await _db.audit_log.find({"tenant_key": tenant_key}).sort("created_at", -1).to_list(limit)
    out = []
    for d in docs:
        d = dict(d)
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out
