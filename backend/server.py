from fastapi import FastAPI, APIRouter, Depends, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from models import (
    StrategyInput, ContentInput, ImageInput, LeadInput, ScrapeLeadsInput, ImportLeadsInput,
    SalesAssistantInput, CampaignInput, CampaignMetricsInput,
    SocialPostInput, SchedulePostInput, CompetitorInput, TrendInput,
    ClientInput, ConnectionInput, PortalUserInput, SendEmailInput, CrmSyncInput,
    ProfileInput, ExtractProfileInput, BudgetPlanInput,
    ProposalGenerateInput, ProposalActionInput, AutopilotConfigInput, now_utc,
)
from engine_models import (
    BrainIngestInput, BrainQueryInput, MissionInput, MissionActionInput,
    LeadEnrichInput, LeadEventsInput, ExperimentInput, ExperimentDecisionInput,
    AttributionTouchInput, RevenueEventInput, PolicyInput,
)
import engine as eng
import agents as ag
from auth import create_auth_router, seed_admin, hash_password
import ai
import intel
import leadsource
import secrets_store as ss
import integrations_live as live

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.users.create_index("email", unique=True)
    await seed_admin(db)
    await seed_email_connection(db)
    await seed_twilio_verify_connection(db)
    try:
        eng.bind_db(db)
        await eng._ensure_indexes()
        ag.bind_db(db)
        await ag._ensure_indexes()
        ag.start_scheduler()
    except Exception as e:
        logger.warning(f"engine init failed: {e}")
    try:
        await db.brain_chunks.create_index("tenant_key")
        await db.brain_chunks.create_index("keywords")
        await db.brain_chunks.create_index("embedding")
    except Exception as e:
        logger.warning(f"vector indexes failed: {e}")
    creds = ROOT_DIR.parent / "memory" / "test_credentials.md"
    try:
        creds.write_text(
            "# Test Credentials\n\n"
            "## Admin\n"
            f"- Email: {os.environ.get('ADMIN_EMAIL')}\n"
            f"- Password: {os.environ.get('ADMIN_PASSWORD')}\n"
            f"- Phone (OTP/SMS): {os.environ.get('ADMIN_PHONE')}\n"
            "- Role: admin\n\n"
            "## Auth endpoints\n"
            "- POST /api/auth/register\n- POST /api/auth/login\n"
            "- POST /api/auth/logout\n- GET /api/auth/me\n"
            "- POST /api/auth/otp/request  (email -> SMTP code; phone -> Twilio Verify SMS)\n"
            "- POST /api/auth/otp/verify\n"
        )
    except Exception as e:
        logger.warning(f"could not write creds: {e}")
    autopilot_task = asyncio.create_task(_autopilot_loop())
    yield
    autopilot_task.cancel()
    ag.stop_scheduler()
    client.close()


async def _autopilot_loop():
    """Daily autopilot: generate campaign proposals for autopilot-enabled profiles (human-approved)."""
    import asyncio as _a
    while True:
        try:
            profiles = await db.profiles.find({"autopilot": True}).to_list(500)
            today = now_utc().date().isoformat()
            cap = await _get_autopilot_cap()
            for pr in profiles:
                if pr.get("last_autopilot") == today:
                    continue
                owner_id = pr.get("user_id")
                cid = pr.get("client_id")
                per_day = max(1, min(int(pr.get("daily_proposals", 3) or 3), cap))
                pending = await db.proposals.count_documents({"user_id": owner_id, "client_id": cid, "status": "Pending"})
                if pending < 5:
                    await _generate_proposals(owner_id, cid, per_day)
                await db.profiles.update_one({"_id": pr["_id"]}, {"$set": {"last_autopilot": today}})
        except Exception as e:
            logger.warning(f"autopilot loop error: {e}")
        await _a.sleep(6 * 3600)  # re-check every 6h; gated to once/day per profile


app = FastAPI(lifespan=lifespan)

auth_router, get_current_user = create_auth_router(db)
api = APIRouter(prefix="/api")


def _clean_value(v):
    if hasattr(v, "__class__") and v.__class__.__name__ == "ObjectId":
        return str(v)
    if isinstance(v, list):
        return [_clean_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _clean_value(x) for k, x in v.items()}
    return v


def _serialize(doc: dict) -> dict:
    if not doc:
        return doc
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return _clean_value(doc)


def _owner(user: dict) -> str:
    """Owner account id — client-portal users inherit their owner's data scope."""
    return user.get("owner_id") or str(user["_id"])


def _require_owner(user: dict):
    if user.get("role") == "client":
        raise HTTPException(403, "Not permitted for client portal accounts")


def _scoped_client(user: dict, client_id: str = None) -> str:
    """Client portal users are always locked to their own client_id."""
    if user.get("role") == "client":
        return user.get("client_id")
    return client_id


async def _get_scoped(collection, doc_id: str, user: dict):
    """Fetch a doc by id and enforce owner + (for portal users) client_id scope."""
    try:
        doc = await collection.find_one({"_id": ObjectId(doc_id)})
    except Exception:
        raise HTTPException(400, "Invalid id")
    if not doc or doc.get("user_id") != _owner(user):
        raise HTTPException(404, "Not found")
    if user.get("role") == "client" and doc.get("client_id") != user.get("client_id"):
        raise HTTPException(403, "Not permitted")
    return doc


async def seed_email_connection(db):
    """Seed a platform-level SMTP email connection from env (AIMarketing brand)."""
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").lower()
    admin = await db.users.find_one({"email": admin_email})
    if not admin or not os.environ.get("SMTP_USER"):
        return
    owner_id = str(admin["_id"])
    existing = await db.connections.find_one({"user_id": owner_id, "client_id": None, "provider": "email"})
    if existing:
        return
    creds = {
        "smtp_host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": os.environ.get("SMTP_PORT", "587"),
        "smtp_user": os.environ.get("SMTP_USER", ""),
        "smtp_password": os.environ.get("SMTP_PASSWORD", ""),
        "from_email": os.environ.get("EMAIL_FROM", os.environ.get("SMTP_USER", "")),
        "from_name": os.environ.get("EMAIL_FROM_NAME", "AIMarketing"),
    }
    enc = {k: ss.encrypt(str(v)) for k, v in creds.items() if v}
    await db.connections.insert_one({
        "user_id": owner_id, "client_id": None, "provider": "email",
        "credentials": enc, "updated_at": now_utc().isoformat(),
    })


async def seed_twilio_verify_connection(db):
    """Seed a platform-level Twilio Verify connection from env (system OTP sender)."""
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").lower()
    admin = await db.users.find_one({"email": admin_email})
    if not admin or not os.environ.get("TWILIO_ACCOUNT_SID"):
        return
    owner_id = str(admin["_id"])
    creds = {
        "account_sid": os.environ.get("TWILIO_ACCOUNT_SID", ""),
        "auth_token": os.environ.get("TWILIO_AUTH_TOKEN", ""),
        "verify_service_sid": os.environ.get("TWILIO_VERIFY_SERVICE_SID", ""),
    }
    if not all(creds.values()):
        return
    enc = {k: ss.encrypt(str(v)) for k, v in creds.items()}
    await db.connections.update_one(
        {"user_id": owner_id, "client_id": None, "provider": "twilio_verify"},
        {"$set": {"user_id": owner_id, "client_id": None, "provider": "twilio_verify",
                  "credentials": enc, "updated_at": now_utc().isoformat()}},
        upsert=True,
    )


AUTOPILOT_DEFAULT_CAP = 10


def _is_admin(user: dict) -> bool:
    return user.get("role") == "admin"


def _require_admin(user: dict):
    if not _is_admin(user):
        raise HTTPException(403, "Admin only")


async def _get_autopilot_cap() -> int:
    doc = await db.settings.find_one({"key": "autopilot_cap"})
    try:
        return min(50, max(1, int(doc["value"]))) if doc else AUTOPILOT_DEFAULT_CAP
    except Exception:
        return AUTOPILOT_DEFAULT_CAP



@api.get("/")
async def root():
    return {"message": "AI Marketing Engine API", "status": "online"}


# ---------------- STRATEGY ----------------
@api.post("/strategy/generate")
async def generate_strategy(data: StrategyInput, user: dict = Depends(get_current_user)):
    system = (
        "You are an elite Chief Marketing Officer AI. You build comprehensive, "
        "data-driven, autonomous marketing strategies for enterprises."
    )
    prompt = f"""Create a complete autonomous marketing strategy.
Industry: {data.industry}
Product: {data.product}
Competitors: {data.competitors}
Budget: {data.budget}
Geography: {data.geography}
Goals: {data.goals}

Return JSON with EXACTLY this shape:
{{
  "executive_summary": "2-3 sentence overview",
  "gtm_strategy": "go-to-market approach paragraph",
  "target_audience": "who to target",
  "personas": [{{"name":"","role":"","pain_points":"","channels":""}}],
  "channel_mix": [{{"channel":"","allocation_pct":30,"rationale":""}}],
  "campaign_calendar": [{{"quarter":"Q1","theme":"","key_campaigns":""}}],
  "budget_allocation": [{{"category":"","pct":30,"amount":"","note":""}}],
  "kpis": [{{"metric":"","target":""}}],
  "quarterly_roadmap": [{{"quarter":"Q1","objectives":"","milestones":""}}]
}}
Ensure channel_mix allocation_pct sums to 100 and budget_allocation pct sums to 100."""
    result = await ai.generate_json(f"strategy-{user['_id']}", system, prompt)
    doc = {
        "user_id": _owner(user),
        "input": data.model_dump(),
        "result": result,
        "created_at": now_utc().isoformat(),
    }
    res = await db.strategies.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize(doc)


@api.get("/strategy")
async def list_strategies(user: dict = Depends(get_current_user)):
    docs = await db.strategies.find({"user_id": _owner(user)}).sort("created_at", -1).to_list(100)
    return [_serialize(d) for d in docs]


@api.get("/strategy/{sid}")
async def get_strategy(sid: str, user: dict = Depends(get_current_user)):
    doc = await db.strategies.find_one({"_id": ObjectId(sid)})
    if not doc:
        raise HTTPException(404, "Not found")
    return _serialize(doc)


# ---------------- CONTENT STUDIO ----------------
@api.post("/content/generate")
async def generate_content(data: ContentInput, user: dict = Depends(get_current_user)):
    system = (
        "You are an award-winning marketing copywriter and content strategist. "
        "You produce SEO-optimized, brand-compliant, high-converting content."
    )
    prompt = f"""Generate a {data.content_type} about "{data.topic}".
Tone: {data.tone}. Language: {data.language}. Target keywords: {data.keywords or 'auto'}.

Return JSON:
{{
  "title": "",
  "body": "the full content, use \\n for line breaks",
  "hashtags": ["#tag1","#tag2"],
  "seo_keywords": ["kw1","kw2"],
  "cta": "call to action",
  "meta_description": ""
}}"""
    result = await ai.generate_json(f"content-{user['_id']}", system, prompt)
    doc = {
        "user_id": _owner(user),
        "kind": "text",
        "content_type": data.content_type,
        "topic": data.topic,
        "result": result,
        "created_at": now_utc().isoformat(),
    }
    res = await db.content.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize(doc)


@api.post("/content/image")
async def generate_creative(data: ImageInput, user: dict = Depends(get_current_user)):
    full_prompt = f"{data.prompt}. Style: {data.style}. High quality, professional marketing creative, no watermark."
    image_url = await ai.generate_image(f"img-{user['_id']}", full_prompt)
    if not image_url:
        raise HTTPException(500, "Image generation failed")
    doc = {
        "user_id": _owner(user),
        "kind": "image",
        "content_type": "creative",
        "topic": data.prompt,
        "result": {"image_url": image_url, "style": data.style},
        "created_at": now_utc().isoformat(),
    }
    res = await db.content.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize(doc)


@api.get("/content")
async def list_content(user: dict = Depends(get_current_user)):
    docs = await db.content.find({"user_id": _owner(user)}).sort("created_at", -1).to_list(200)
    return [_serialize(d) for d in docs]


# ---------------- LEADS ----------------
@api.post("/leads")
async def create_lead(data: LeadInput, user: dict = Depends(get_current_user)):
    payload = data.model_dump()
    payload["client_id"] = _scoped_client(user, payload.get("client_id"))
    doc = {
        "user_id": _owner(user),
        **payload,
        "score": None,
        "category": "Unscored",
        "reasoning": "",
        "stage": "New",
        "created_at": now_utc().isoformat(),
    }
    res = await db.leads.insert_one(doc)
    doc["_id"] = res.inserted_id
    try:
        await eng.emit_event(user, "LeadCreated", entity_type="lead",
                             entity_id=str(res.inserted_id),
                             payload={"name": payload.get("name"), "company": payload.get("company"),
                                      "source": payload.get("source")})
    except Exception:
        pass
    return _serialize(doc)


@api.get("/leads")
async def list_leads(client_id: str = None, user: dict = Depends(get_current_user)):
    q = {"user_id": _owner(user)}
    cid = _scoped_client(user, client_id)
    if cid:
        q["client_id"] = cid
    docs = await db.leads.find(q).sort("created_at", -1).to_list(1000)
    return [_serialize(d) for d in docs]


@api.post("/leads/scrape")
async def scrape_leads(data: ScrapeLeadsInput, user: dict = Depends(get_current_user)):
    domains = [d for d in data.domains.replace(",", "\n").splitlines() if d.strip()][:10]
    if not domains:
        raise HTTPException(400, "Provide at least one domain")
    scraped = await leadsource.scrape_domains(domains)
    created = []
    skipped = 0
    for s in scraped:
        if not s.get("found"):
            skipped += 1
            continue
        doc = {
            "user_id": _owner(user),
            "client_id": data.client_id,
            "name": s["name"], "email": s["email"], "company": s["company"],
            "role": s.get("role", ""), "industry": "", "company_size": "",
            "budget": "", "source": "Web Scrape", "notes": s["notes"],
            "score": None, "category": "Unscored", "reasoning": "", "stage": "New",
            "created_at": now_utc().isoformat(),
        }
        res = await db.leads.insert_one(doc)
        doc["_id"] = res.inserted_id
        created.append(_serialize(doc))
    return {"created": created, "count": len(created), "skipped": skipped}


@api.post("/leads/import")
async def import_leads(data: ImportLeadsInput, user: dict = Depends(get_current_user)):
    rows = leadsource.parse_csv(data.csv_text)
    if not rows:
        raise HTTPException(400, "No valid rows found. Ensure the CSV has a header row with name/email/company.")
    created = 0
    for r in rows[:500]:
        doc = {
            "user_id": _owner(user),
            "client_id": data.client_id,
            **r,
            "score": None, "category": "Unscored", "reasoning": "", "stage": "New",
            "created_at": now_utc().isoformat(),
        }
        await db.leads.insert_one(doc)
        created += 1
    return {"count": created}


@api.post("/leads/{lead_id}/score")
async def score_lead(lead_id: str, user: dict = Depends(get_current_user)):
    lead = await _get_scoped(db.leads, lead_id, user)
    system = "You are an AI lead qualification engine. You score B2B leads objectively from 0-100."
    prompt = f"""Score this lead:
Name: {lead.get('name')}, Company: {lead.get('company')}, Role: {lead.get('role')}
Industry: {lead.get('industry')}, Company size: {lead.get('company_size')}
Budget: {lead.get('budget')}, Source: {lead.get('source')}, Notes: {lead.get('notes')}

Return JSON:
{{"score": 0-100, "category": "Hot|Warm|Cold|Sales Ready", "reasoning": "1-2 sentences"}}"""
    result = await ai.generate_json(f"score-{lead_id}", system, prompt)
    score = result.get("score", 50)
    category = result.get("category", "Warm")
    reasoning = result.get("reasoning", "")
    await db.leads.update_one(
        {"_id": ObjectId(lead_id)},
        {"$set": {"score": score, "category": category, "reasoning": reasoning}},
    )
    lead = await db.leads.find_one({"_id": ObjectId(lead_id)})
    return _serialize(lead)


@api.patch("/leads/{lead_id}/stage")
async def update_stage(lead_id: str, body: dict, user: dict = Depends(get_current_user)):
    await _get_scoped(db.leads, lead_id, user)
    await db.leads.update_one({"_id": ObjectId(lead_id)}, {"$set": {"stage": body.get("stage")}})
    lead = await db.leads.find_one({"_id": ObjectId(lead_id)})
    return _serialize(lead)


@api.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, user: dict = Depends(get_current_user)):
    await _get_scoped(db.leads, lead_id, user)
    await db.leads.delete_one({"_id": ObjectId(lead_id)})
    return {"message": "deleted"}


# ---------------- SALES ASSISTANT ----------------
@api.post("/sales/assist")
async def sales_assist(data: SalesAssistantInput, user: dict = Depends(get_current_user)):
    lead = await _get_scoped(db.leads, data.lead_id, user)
    action_map = {
        "follow_up_email": "Write a persuasive, personalized follow-up email",
        "whatsapp": "Write a short, friendly WhatsApp follow-up message",
        "objection_handling": "Provide objection-handling talking points for common objections",
        "summary": "Write a concise conversation summary and recommended next best action",
    }
    task = action_map.get(data.action, action_map["follow_up_email"])
    system = "You are an AI Sales Assistant that nurtures and converts B2B leads with empathetic, results-driven communication."
    prompt = f"""{task} for this lead:
Name: {lead.get('name')}, Company: {lead.get('company')}, Role: {lead.get('role')}
Industry: {lead.get('industry')}, Category: {lead.get('category')}, Notes: {lead.get('notes')}

Return JSON: {{"title":"", "message":"full text, use \\n for line breaks"}}"""
    result = await ai.generate_json(f"sales-{data.lead_id}", system, prompt)
    return {"lead": _serialize(lead), "action": data.action, "result": result}


# ---------------- CAMPAIGNS (real tracker) ----------------
def _campaign_derived(doc: dict) -> dict:
    imp = doc.get("impressions", 0) or 0
    clk = doc.get("clicks", 0) or 0
    conv = doc.get("conversions", 0) or 0
    budget = doc.get("budget", 0) or 0
    rev = doc.get("revenue", 0) or 0
    doc["ctr"] = round(clk / imp * 100, 2) if imp else 0
    doc["cpc"] = round(budget / clk, 2) if clk else 0
    doc["cpa"] = round(budget / conv, 2) if conv else 0
    doc["roas"] = round(rev / budget, 2) if budget else 0
    doc["roi"] = round((rev - budget) / budget * 100, 1) if budget else 0
    return doc


@api.post("/campaigns")
async def create_campaign(data: CampaignInput, user: dict = Depends(get_current_user)):
    doc = {
        "user_id": _owner(user),
        **data.model_dump(),
        "status": "Active",
        "created_at": now_utc().isoformat(),
    }
    res = await db.campaigns.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize(_campaign_derived(doc))


@api.get("/campaigns")
async def list_campaigns(client_id: str = None, user: dict = Depends(get_current_user)):
    q = {"user_id": _owner(user)}
    cid = _scoped_client(user, client_id)
    if cid:
        q["client_id"] = cid
    docs = await db.campaigns.find(q).sort("created_at", -1).to_list(200)
    return [_serialize(_campaign_derived(d)) for d in docs]


@api.patch("/campaigns/{cid}/metrics")
async def update_metrics(cid: str, data: CampaignMetricsInput, user: dict = Depends(get_current_user)):
    await _get_scoped(db.campaigns, cid, user)
    await db.campaigns.update_one({"_id": ObjectId(cid)}, {"$set": data.model_dump()})
    c = await db.campaigns.find_one({"_id": ObjectId(cid)})
    return _serialize(_campaign_derived(c))


@api.patch("/campaigns/{cid}/toggle")
async def toggle_campaign(cid: str, user: dict = Depends(get_current_user)):
    c = await _get_scoped(db.campaigns, cid, user)
    new_status = "Paused" if c.get("status") == "Active" else "Active"
    await db.campaigns.update_one({"_id": ObjectId(cid)}, {"$set": {"status": new_status}})
    c = await db.campaigns.find_one({"_id": ObjectId(cid)})
    return _serialize(_campaign_derived(c))


@api.delete("/campaigns/{cid}")
async def delete_campaign(cid: str, user: dict = Depends(get_current_user)):
    await _get_scoped(db.campaigns, cid, user)
    await db.campaigns.delete_one({"_id": ObjectId(cid)})
    return {"message": "deleted"}


# ---------------- SOCIAL MEDIA MANAGER ----------------
@api.post("/social/generate")
async def social_generate(data: SocialPostInput, user: dict = Depends(get_current_user)):
    system = f"You are a social media expert who writes high-engagement {data.platform} posts."
    prompt = f"""Write a {data.tone} {data.platform} post about "{data.topic}".
Return JSON: {{"content":"the post text", "hashtags":["#a","#b"], "best_time":"suggested posting time e.g. Tue 10:00 AM"}}"""
    result = await ai.generate_json(f"social-{user['_id']}", system, prompt)
    return result


@api.post("/social/schedule")
async def social_schedule(data: SchedulePostInput, user: dict = Depends(get_current_user)):
    doc = {
        "user_id": _owner(user),
        "platform": data.platform,
        "content": data.content,
        "scheduled_time": data.scheduled_time,
        "status": "Scheduled",
        "created_at": now_utc().isoformat(),
    }
    res = await db.social_posts.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize(doc)


@api.get("/social/posts")
async def social_posts(user: dict = Depends(get_current_user)):
    docs = await db.social_posts.find({"user_id": _owner(user)}).sort("scheduled_time", 1).to_list(300)
    return [_serialize(d) for d in docs]


@api.patch("/social/posts/{pid}/publish")
async def social_publish(pid: str, user: dict = Depends(get_current_user)):
    p = await _get_scoped(db.social_posts, pid, user)
    provider = live.PLATFORM_PROVIDER.get(p.get("platform"))
    if not provider:
        raise HTTPException(400, f"Publishing to {p.get('platform')} is not supported yet.")
    creds = await live.get_credentials(db, _owner(user), provider, p.get("client_id"))
    if not creds:
        raise HTTPException(400, f"{p.get('platform')} is not connected. Add credentials in Settings to publish.")
    try:
        ok, info = await live.social_publish(provider, creds, p.get("content", ""))
    except Exception as e:
        raise HTTPException(502, f"{provider} publish error: {str(e)[:200]}")
    if not ok:
        raise HTTPException(502, f"{provider} rejected the post: {str(info)[:200]}")
    await db.social_posts.update_one(
        {"_id": ObjectId(pid)},
        {"$set": {"status": "Published", "published_at": now_utc().isoformat(),
                  "published_mode": "live", "publish_detail": str(info)[:200]}},
    )
    p = await db.social_posts.find_one({"_id": ObjectId(pid)})
    return _serialize(p)


@api.delete("/social/posts/{pid}")
async def social_delete(pid: str, user: dict = Depends(get_current_user)):
    await db.social_posts.delete_one({"_id": ObjectId(pid)})
    return {"message": "deleted"}


# ---------------- ANALYTICS (computed from real data) ----------------
@api.get("/analytics/overview")
async def analytics_overview(user: dict = Depends(get_current_user)):
    uid = _owner(user)
    base = {"user_id": uid}
    cid = _scoped_client(user, None)
    if cid:
        base["client_id"] = cid
    leads = await db.leads.find(base).to_list(2000)
    campaigns = await db.campaigns.find(base).to_list(500)
    content_count = await db.content.count_documents({"user_id": uid})
    strategy_count = await db.strategies.count_documents({"user_id": uid})

    total_spend = sum(c.get("budget", 0) or 0 for c in campaigns)
    total_conversions = sum(c.get("conversions", 0) or 0 for c in campaigns)
    total_clicks = sum(c.get("clicks", 0) or 0 for c in campaigns)
    total_impressions = sum(c.get("impressions", 0) or 0 for c in campaigns)
    revenue = sum(c.get("revenue", 0) or 0 for c in campaigns)
    hot = len([l for l in leads if l.get("category") in ("Hot", "Sales Ready")])
    won = len([l for l in leads if l.get("stage") == "Won"])
    opps = len([l for l in leads if l.get("stage") in ("Opportunity", "Won")])

    cac = round(total_spend / total_conversions, 2) if total_conversions else 0
    roi = round((revenue - total_spend) / total_spend * 100, 1) if total_spend else 0
    ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions else 0

    # Real monthly trend from lead/campaign created_at (last 6 months)
    from datetime import datetime as _dt
    now = now_utc()
    months = []
    for i in range(5, -1, -1):
        m = (now.month - i - 1) % 12 + 1
        y = now.year + ((now.month - i - 1) // 12)
        months.append((y, m))

    def _month_key(iso):
        try:
            d = _dt.fromisoformat(iso)
            return (d.year, d.month)
        except Exception:
            return None

    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    trend = []
    for (y, m) in months:
        mleads = [l for l in leads if _month_key(l.get("created_at", "")) == (y, m)]
        mcamps = [c for c in campaigns if _month_key(c.get("created_at", "")) == (y, m)]
        trend.append({
            "month": labels[m - 1],
            "leads": len(mleads),
            "conversions": sum(c.get("conversions", 0) or 0 for c in mcamps),
            "revenue": sum(c.get("revenue", 0) or 0 for c in mcamps),
        })

    # Channel performance from real campaigns grouped by channel
    ch_map = {}
    for c in campaigns:
        ch = c.get("channel", "Other")
        e = ch_map.setdefault(ch, {"channel": ch, "spend": 0, "revenue": 0})
        e["spend"] += c.get("budget", 0) or 0
        e["revenue"] += c.get("revenue", 0) or 0
    channel_perf = []
    for e in ch_map.values():
        e["roas"] = round(e["revenue"] / e["spend"], 2) if e["spend"] else 0
        channel_perf.append(e)

    funnel = [
        {"stage": "Impressions", "value": total_impressions},
        {"stage": "Leads", "value": len(leads)},
        {"stage": "Qualified", "value": hot},
        {"stage": "Opportunities", "value": opps},
        {"stage": "Customers", "value": max(won, total_conversions)},
    ]

    return {
        "kpis": {
            "total_leads": len(leads),
            "hot_leads": hot,
            "campaigns": len(campaigns),
            "content_generated": content_count,
            "strategies": strategy_count,
            "total_spend": round(total_spend, 2),
            "revenue": round(revenue, 2),
            "cac": cac,
            "roi": roi,
            "ctr": ctr,
            "conversions": total_conversions,
        },
        "trend": trend,
        "channel_performance": channel_perf,
        "funnel": funnel,
    }


# ---------------- COMPETITOR INTELLIGENCE (real web fetch + AI) ----------------
@api.post("/competitors")
async def add_competitor(data: CompetitorInput, user: dict = Depends(get_current_user)):
    try:
        analysis = await intel.analyze_competitor(data.name, data.url)
    except Exception as e:
        logger.error(f"competitor analyze failed: {e}")
        raise HTTPException(502, f"Could not fetch or analyze {data.url}")
    doc = {
        "user_id": _owner(user),
        "name": data.name,
        "url": data.url,
        "analysis": analysis,
        "history": [{"at": now_utc().isoformat(), "analysis": analysis}],
        "created_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
    }
    res = await db.competitors.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize(doc)


@api.get("/competitors")
async def list_competitors(user: dict = Depends(get_current_user)):
    docs = await db.competitors.find({"user_id": _owner(user)}).sort("created_at", -1).to_list(100)
    return [_serialize(d) for d in docs]


@api.post("/competitors/{cid}/rescan")
async def rescan_competitor(cid: str, user: dict = Depends(get_current_user)):
    c = await db.competitors.find_one({"_id": ObjectId(cid)})
    if not c:
        raise HTTPException(404, "Not found")
    try:
        analysis = await intel.analyze_competitor(c["name"], c["url"])
    except Exception as e:
        raise HTTPException(502, f"Rescan failed: {e}")
    hist = c.get("history", [])
    hist.append({"at": now_utc().isoformat(), "analysis": analysis})
    await db.competitors.update_one(
        {"_id": ObjectId(cid)},
        {"$set": {"analysis": analysis, "history": hist[-10:], "updated_at": now_utc().isoformat()}},
    )
    c = await db.competitors.find_one({"_id": ObjectId(cid)})
    return _serialize(c)


@api.delete("/competitors/{cid}")
async def delete_competitor(cid: str, user: dict = Depends(get_current_user)):
    await db.competitors.delete_one({"_id": ObjectId(cid)})
    return {"message": "deleted"}


@api.post("/trends/discover")
async def discover_trends(data: TrendInput, user: dict = Depends(get_current_user)):
    try:
        result = await intel.discover_trends(data.industry)
    except Exception as e:
        logger.error(f"trends failed: {e}")
        raise HTTPException(502, "Could not fetch trends")
    return result


# ---------------- CLIENTS (Agency customer accounts) ----------------
@api.post("/clients")
async def create_client(data: ClientInput, user: dict = Depends(get_current_user)):
    _require_owner(user)
    doc = {"user_id": _owner(user), **data.model_dump(), "created_at": now_utc().isoformat()}
    res = await db.clients.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize(doc)


@api.get("/clients")
async def list_clients(user: dict = Depends(get_current_user)):
    _require_owner(user)
    docs = await db.clients.find({"user_id": _owner(user)}).sort("created_at", -1).to_list(200)
    out = []
    for d in docs:
        s = _serialize(d)
        s["leads"] = await db.leads.count_documents({"user_id": _owner(user), "client_id": s["id"]})
        s["campaigns"] = await db.campaigns.count_documents({"user_id": _owner(user), "client_id": s["id"]})
        s["connections"] = await db.connections.count_documents({"user_id": _owner(user), "client_id": s["id"]})
        s["portal_users"] = await db.users.count_documents({"owner_id": _owner(user), "client_id": s["id"]})
        out.append(s)
    return out


@api.patch("/clients/{cid}")
async def update_client(cid: str, data: ClientInput, user: dict = Depends(get_current_user)):
    _require_owner(user)
    await db.clients.update_one({"_id": ObjectId(cid)}, {"$set": data.model_dump()})
    c = await db.clients.find_one({"_id": ObjectId(cid)})
    return _serialize(c)


@api.delete("/clients/{cid}")
async def delete_client(cid: str, user: dict = Depends(get_current_user)):
    _require_owner(user)
    await db.clients.delete_one({"_id": ObjectId(cid)})
    return {"message": "deleted"}


@api.post("/clients/{cid}/portal-user")
async def create_portal_user(cid: str, data: PortalUserInput, user: dict = Depends(get_current_user)):
    _require_owner(user)
    client = await db.clients.find_one({"_id": ObjectId(cid), "user_id": _owner(user)})
    if not client:
        raise HTTPException(404, "Client not found")
    email = data.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already in use")
    await db.users.insert_one({
        "email": email,
        "password_hash": hash_password(data.password),
        "name": data.name or client.get("name", "Client"),
        "role": "client",
        "owner_id": _owner(user),
        "client_id": cid,
        "created_at": now_utc().isoformat(),
    })
    return {"message": "Portal login created", "email": email}


@api.get("/clients/{cid}/portal-users")
async def list_portal_users(cid: str, user: dict = Depends(get_current_user)):
    _require_owner(user)
    docs = await db.users.find({"owner_id": _owner(user), "client_id": cid}).to_list(100)
    return [{"id": str(d["_id"]), "email": d["email"], "name": d.get("name", "")} for d in docs]


# ---------------- INTEGRATIONS / CONNECTIONS (encrypted placeholders) ----------------
@api.get("/integrations/providers")
async def integration_providers(user: dict = Depends(get_current_user)):
    _require_owner(user)
    return ss.PROVIDERS


@api.get("/connections")
async def list_connections(client_id: str = None, user: dict = Depends(get_current_user)):
    _require_owner(user)
    q = {"user_id": _owner(user)}
    q["client_id"] = client_id if client_id else None
    docs = await db.connections.find(q).to_list(200)
    by_provider = {d["provider"]: d for d in docs}
    result = []
    for p in ss.PROVIDERS:
        conn = by_provider.get(p["id"])
        creds_status = {}
        configured = False
        if conn:
            stored = conn.get("credentials", {})
            for f in p["fields"]:
                dec = ss.decrypt(stored.get(f, ""))
                creds_status[f] = {"set": bool(dec), "hint": ss.mask(dec)}
            configured = all(creds_status[f]["set"] for f in p["fields"])
        else:
            creds_status = {f: {"set": False, "hint": ""} for f in p["fields"]}
        result.append({
            "provider": p["id"], "label": p["label"], "category": p["category"],
            "fields": p["fields"], "help": p["help"],
            "status": "Connected" if configured else ("Partial" if conn else "Pending"),
            "credentials": creds_status,
            "updated_at": conn.get("updated_at") if conn else None,
        })
    return result


@api.post("/connections")
async def save_connection(data: ConnectionInput, user: dict = Depends(get_current_user)):
    _require_owner(user)
    provider = ss.PROVIDER_MAP.get(data.provider)
    if not provider:
        raise HTTPException(400, "Unknown provider")
    cid = data.client_id if data.client_id else None
    existing = await db.connections.find_one({"user_id": _owner(user), "client_id": cid, "provider": data.provider})
    stored = existing.get("credentials", {}) if existing else {}
    for f in provider["fields"]:
        val = data.credentials.get(f)
        if val:  # only overwrite when a new non-empty value is provided
            stored[f] = ss.encrypt(str(val))
    doc = {
        "user_id": _owner(user), "client_id": cid, "provider": data.provider,
        "credentials": stored, "updated_at": now_utc().isoformat(),
    }
    await db.connections.update_one(
        {"user_id": _owner(user), "client_id": cid, "provider": data.provider},
        {"$set": doc}, upsert=True,
    )
    return {"message": "saved", "provider": data.provider}


@api.delete("/connections/{provider}")
async def delete_connection(provider: str, client_id: str = None, user: dict = Depends(get_current_user)):
    _require_owner(user)
    await db.connections.delete_one({"user_id": _owner(user), "client_id": client_id if client_id else None, "provider": provider})
    return {"message": "deleted"}


# ---------------- LIVE: EMAIL SEND + CRM SYNC (use vault credentials) ----------------
@api.post("/sales/send-email")
async def send_email_endpoint(data: SendEmailInput, user: dict = Depends(get_current_user)):
    lead = await _get_scoped(db.leads, data.lead_id, user)
    if not lead.get("email"):
        raise HTTPException(400, "This lead has no email address")
    creds = await live.get_credentials(db, _owner(user), "email", lead.get("client_id"))
    if not creds:
        raise HTTPException(400, "Email is not configured. Add SMTP credentials in Settings.")
    try:
        ok, detail = await live.send_email(creds, lead["email"], data.subject, data.message)
    except Exception as e:
        raise HTTPException(502, f"Send failed: {str(e)[:200]}")
    log = {
        "user_id": _owner(user), "client_id": lead.get("client_id"),
        "lead_id": data.lead_id, "to": lead["email"], "subject": data.subject,
        "status": "sent" if ok else "failed", "detail": str(detail)[:300],
        "created_at": now_utc().isoformat(),
    }
    await db.email_logs.insert_one(log)
    if not ok:
        raise HTTPException(502, f"Send failed: {str(detail)[:200]}")
    return {"message": f"Email sent to {lead['email']}", "status": "sent"}


@api.post("/crm/sync")
async def crm_sync_endpoint(data: CrmSyncInput, user: dict = Depends(get_current_user)):
    if data.provider not in ("hubspot", "zoho"):
        raise HTTPException(400, "Unsupported CRM provider")
    cid = _scoped_client(user, data.client_id)
    creds = await live.get_credentials(db, _owner(user), data.provider, cid)
    if not creds:
        raise HTTPException(400, f"{data.provider.title()} is not configured. Add credentials in Settings.")
    try:
        rows = await live.crm_sync(data.provider, creds)
    except Exception as e:
        raise HTTPException(502, f"CRM sync failed: {str(e)[:200]}")
    imported = 0
    for r in rows:
        if r.get("email") and await db.leads.find_one({"user_id": _owner(user), "email": r["email"], "client_id": cid}):
            continue
        await db.leads.insert_one({
            "user_id": _owner(user), "client_id": cid, **r,
            "score": None, "category": "Unscored", "reasoning": "", "stage": "New",
            "created_at": now_utc().isoformat(),
        })
        imported += 1
    return {"message": f"Synced {imported} new lead(s) from {data.provider.title()}", "count": imported}


# ---------------- BUSINESS PROFILE + CURRENCY ----------------
@api.get("/profile")
async def get_profile(client_id: str = None, user: dict = Depends(get_current_user)):
    cid = _scoped_client(user, client_id)
    doc = await db.profiles.find_one({"user_id": _owner(user), "client_id": cid})
    if not doc:
        return {"company_name": "", "description": "", "industry": "", "website": "",
                "country": "United States", "currency": "USD", "client_id": cid}
    return _serialize(doc)


@api.put("/profile")
async def save_profile(data: ProfileInput, user: dict = Depends(get_current_user)):
    payload = data.model_dump()
    cid = _scoped_client(user, payload.pop("client_id", None))
    payload["updated_at"] = now_utc().isoformat()
    await db.profiles.update_one(
        {"user_id": _owner(user), "client_id": cid},
        {"$set": {**payload, "user_id": _owner(user), "client_id": cid}},
        upsert=True,
    )
    doc = await db.profiles.find_one({"user_id": _owner(user), "client_id": cid})
    return _serialize(doc)


@api.post("/profile/extract")
async def extract_profile(data: ExtractProfileInput, user: dict = Depends(get_current_user)):
    _require_owner(user)
    try:
        text = await intel.fetch_site_text(data.url)
    except Exception:
        raise HTTPException(502, f"Could not fetch {data.url}")
    system = "You extract structured business profile data from website content."
    prompt = f"""From this website content for {data.url}, extract a business profile.

{text}

Return JSON:
{{"company_name":"", "description":"1-2 sentence summary of what they do", "industry":"", "suggested_country":"best guess country or 'United States'", "suggested_currency":"ISO 4217 code e.g. USD/EUR/GBP/INR"}}"""
    result = await ai.generate_json(f"profile-{user['_id']}", system, prompt)
    result["website"] = data.url
    return result


# ---------------- BUDGET PLANNER (SEO-led, AI) ----------------
@api.post("/budget/plan")
async def budget_plan(data: BudgetPlanInput, user: dict = Depends(get_current_user)):
    cid = _scoped_client(user, data.client_id)
    profile = await db.profiles.find_one({"user_id": _owner(user), "client_id": cid}) or {}
    currency = profile.get("currency", "USD")
    industry = profile.get("industry", "")
    country = profile.get("country", "")
    system = (
        "You are a budget optimization engine. Your philosophy: SEO and organic content are the FOUNDATION "
        "and should receive the LARGEST share of budget for durable, compounding lead generation. Paid marketing "
        "(Google/Meta/LinkedIn ads, retargeting) is used to SUPPORT and accelerate lead flow while SEO ramps. "
        "Organic (SEO/content) should be roughly 45-60% of spend."
    )
    prompt = f"""Create an SEO-led marketing budget plan.
Total budget: {data.total_budget} {currency} ({data.period})
Primary goal: {data.primary_goal}
Industry: {industry or 'general'}. Market: {country or 'global'}.
Notes: {data.notes}

Return JSON:
{{
  "strategy_summary": "2-3 sentences",
  "philosophy": "why SEO-led backed by paid",
  "allocations": [
    {{"channel":"SEO & Content","type":"Organic","pct":50,"expected_leads":120,"rationale":""}},
    {{"channel":"Google Ads","type":"Paid","pct":18,"expected_leads":60,"rationale":""}}
  ],
  "seo_share_pct": 55,
  "paid_share_pct": 45,
  "expected_total_leads": 300,
  "blended_cac": 42.5,
  "ramp": [{{"month":"Month 1","seo_pct":40,"paid_pct":60,"focus":""}}],
  "kpis": [{{"metric":"Organic traffic","target":""}}]
}}
Ensure allocations pct sum to 100 and Organic types collectively >= 45%."""
    result = await ai.generate_json(f"budget-{user['_id']}", system, prompt)
    # compute currency amounts from pct on the server for accuracy
    if isinstance(result.get("allocations"), list):
        for a in result["allocations"]:
            try:
                a["amount"] = round(float(a.get("pct", 0)) / 100 * data.total_budget, 2)
            except Exception:
                a["amount"] = 0
    doc = {
        "user_id": _owner(user), "client_id": cid,
        "input": data.model_dump(), "currency": currency,
        "result": result, "created_at": now_utc().isoformat(),
    }
    res = await db.budget_plans.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize(doc)


@api.get("/budget/plans")
async def list_budget_plans(client_id: str = None, user: dict = Depends(get_current_user)):
    cid = _scoped_client(user, client_id)
    q = {"user_id": _owner(user)}
    if cid:
        q["client_id"] = cid
    docs = await db.budget_plans.find(q).sort("created_at", -1).to_list(50)
    return [_serialize(d) for d in docs]


# ---------------- AUTONOMOUS FLOW STATUS ----------------
@api.get("/flow/status")
async def flow_status(client_id: str = None, user: dict = Depends(get_current_user)):
    owner = _owner(user)
    cid = _scoped_client(user, client_id)
    base = {"user_id": owner}
    if cid:
        base["client_id"] = cid
    profile = await db.profiles.find_one({"user_id": owner, "client_id": cid}) or {}
    leads = await db.leads.find(base).to_list(2000)
    scored = len([l for l in leads if l.get("score") is not None])
    converted = len([l for l in leads if l.get("stage") == "Won"])
    emails = await db.email_logs.count_documents({"user_id": owner, **({"client_id": cid} if cid else {})})
    steps = [
        {"key": "profile", "label": "Business Profile", "done": bool(profile.get("company_name")), "count": 1 if profile.get("company_name") else 0, "route": "/settings"},
        {"key": "strategy", "label": "Marketing Strategy", "done": False, "count": await db.strategies.count_documents({"user_id": owner}), "route": "/strategy"},
        {"key": "content", "label": "Content & Creatives", "done": False, "count": await db.content.count_documents({"user_id": owner}), "route": "/content"},
        {"key": "budget", "label": "Budget Plan", "done": False, "count": await db.budget_plans.count_documents(base), "route": "/budget"},
        {"key": "campaigns", "label": "Launch Campaigns", "done": False, "count": await db.campaigns.count_documents(base), "route": "/campaigns"},
        {"key": "leads", "label": "Capture Leads", "done": False, "count": len(leads), "route": "/leads"},
        {"key": "score", "label": "Qualify & Score", "done": False, "count": scored, "route": "/leads"},
        {"key": "convert", "label": "Nurture & Convert", "done": False, "count": converted + emails, "route": "/sales"},
        {"key": "report", "label": "Measure & Report", "done": False, "count": 1, "route": "/analytics"},
    ]
    for s in steps:
        if s["key"] != "profile":
            s["done"] = s["count"] > 0
    completed = len([s for s in steps if s["done"]])
    return {"steps": steps, "completed": completed, "total": len(steps),
            "autopilot": bool(profile.get("autopilot"))}


# ---------------- AI CAMPAIGN PROPOSALS + HUMAN APPROVALS ----------------
async def _generate_proposals(owner_id: str, client_id: str = None, count: int = 3) -> int:
    profile = await db.profiles.find_one({"user_id": owner_id, "client_id": client_id}) or {}
    currency = profile.get("currency", "USD")
    industry = profile.get("industry", "general")
    company = profile.get("company_name", "the business")
    system = ("You are an autonomous campaign strategist. Propose concrete, ready-to-launch marketing "
              "campaigns that prioritize SEO/content with paid support, for daily human approval.")
    prompt = f"""Propose {count} distinct marketing campaign ideas for {company} (industry: {industry}).
Currency: {currency}.
Return JSON: {{"proposals":[{{"name":"","channel":"SEO|Google Ads|Meta Ads|LinkedIn Ads|Email|Retargeting","objective":"","suggested_budget":500,"target_audience":"","ad_copy":"1-2 line ad/post copy","expected_leads":20,"rationale":""}}]}}"""
    result = await ai.generate_json(f"proposals-{owner_id}-{client_id}", system, prompt)
    proposals = result.get("proposals", []) if isinstance(result, dict) else []
    created = 0
    for p in proposals[:count]:
        await db.proposals.insert_one({
            "user_id": owner_id, "client_id": client_id, "status": "Pending",
            "source": "autopilot", "data": p, "created_at": now_utc().isoformat(),
        })
        created += 1
    return created


@api.post("/proposals/generate")
async def generate_proposals(data: ProposalGenerateInput, user: dict = Depends(get_current_user)):
    _require_owner(user)
    cid = _scoped_client(user, data.client_id)
    cap = await _get_autopilot_cap()
    profile = await db.profiles.find_one({"user_id": _owner(user), "client_id": cid}) or {}
    per_day = max(1, min(int(profile.get("daily_proposals", 3) or 3), cap))
    n = await _generate_proposals(_owner(user), cid, per_day)
    return {"message": f"{n} proposal(s) generated for approval", "count": n}


@api.get("/autopilot/config")
async def get_autopilot_config(client_id: str = None, user: dict = Depends(get_current_user)):
    cid = _scoped_client(user, client_id)
    cap = await _get_autopilot_cap()
    profile = await db.profiles.find_one({"user_id": _owner(user), "client_id": cid}) or {}
    per_day = max(1, min(int(profile.get("daily_proposals", 3) or 3), cap))
    return {"is_admin": _is_admin(user), "cap": cap,
            "daily_proposals": per_day, "autopilot": bool(profile.get("autopilot"))}


@api.post("/autopilot/config")
async def set_autopilot_config(data: AutopilotConfigInput, user: dict = Depends(get_current_user)):
    _require_owner(user)
    if data.cap is not None and _is_admin(user):
        cap_val = max(1, min(int(data.cap), 50))
        await db.settings.update_one({"key": "autopilot_cap"},
                                     {"$set": {"key": "autopilot_cap", "value": cap_val}}, upsert=True)
    cap = await _get_autopilot_cap()
    if data.daily_proposals is not None:
        cid = _scoped_client(user, data.client_id)
        per_day = max(1, min(int(data.daily_proposals), cap))
        await db.profiles.update_one(
            {"user_id": _owner(user), "client_id": cid},
            {"$set": {"daily_proposals": per_day, "user_id": _owner(user), "client_id": cid}},
            upsert=True,
        )
    return await get_autopilot_config(data.client_id, user)


@api.get("/proposals")
async def list_proposals(status: str = None, client_id: str = None, user: dict = Depends(get_current_user)):
    q = {"user_id": _owner(user)}
    cid = _scoped_client(user, client_id)
    if cid:
        q["client_id"] = cid
    if status:
        q["status"] = status
    docs = await db.proposals.find(q).sort("created_at", -1).to_list(200)
    return [_serialize(d) for d in docs]


@api.post("/proposals/{pid}/approve")
async def approve_proposal(pid: str, body: ProposalActionInput = ProposalActionInput(), user: dict = Depends(get_current_user)):
    _require_owner(user)
    prop = await _get_scoped(db.proposals, pid, user)
    if prop.get("status") != "Pending":
        raise HTTPException(400, "Already processed")
    p = {**prop.get("data", {}), **(body.edits or {})}
    campaign = {
        "user_id": _owner(user), "client_id": prop.get("client_id"),
        "name": p.get("name", "Campaign"), "channel": p.get("channel", "SEO"),
        "objective": p.get("objective", "Lead Generation"),
        "budget": float(p.get("suggested_budget", 0) or 0),
        "impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0.0,
        "status": "Active", "created_at": now_utc().isoformat(),
    }
    res = await db.campaigns.insert_one(campaign)
    await db.proposals.update_one({"_id": ObjectId(pid)}, {"$set": {"status": "Approved", "campaign_id": str(res.inserted_id)}})
    campaign["_id"] = res.inserted_id
    return {"message": "Approved — campaign launched", "campaign": _serialize(_campaign_derived(campaign))}


@api.post("/proposals/{pid}/reject")
async def reject_proposal(pid: str, user: dict = Depends(get_current_user)):
    _require_owner(user)
    await _get_scoped(db.proposals, pid, user)
    await db.proposals.update_one({"_id": ObjectId(pid)}, {"$set": {"status": "Rejected"}})
    return {"message": "Rejected"}


# ---------------- AI AGENTS ----------------
AGENTS = [
    {"name": "Strategy Agent", "role": "Builds autonomous marketing plans", "status": "Active"},
    {"name": "Content Agent", "role": "Generates blogs, posts & emails", "status": "Active"},
    {"name": "Creative Agent", "role": "Designs posters, banners & visuals", "status": "Active"},
    {"name": "SEO Agent", "role": "Optimizes website & keywords", "status": "Active"},
    {"name": "SEM/PPC Agent", "role": "Manages Google & Social ads", "status": "Active"},
    {"name": "Budget Agent", "role": "Reallocates spend by ROI", "status": "Active"},
    {"name": "Lead Agent", "role": "Captures & scores leads", "status": "Active"},
    {"name": "Sales Agent", "role": "Nurtures & converts leads", "status": "Active"},
    {"name": "Social Agent", "role": "Publishes across platforms", "status": "Idle"},
    {"name": "Analytics Agent", "role": "Insights & dashboards", "status": "Active"},
    {"name": "Competitor Agent", "role": "Market & competitor intel", "status": "Idle"},
    {"name": "Learning Agent", "role": "Self-optimizes continuously", "status": "Active"},
]


@api.get("/agents")
async def list_agents(user: dict = Depends(get_current_user)):
    return AGENTS


# ---------------- MODULE A: BUSINESS BRAIN / RAG ----------------
@api.post("/brain/ingest")
async def brain_ingest_route(data: BrainIngestInput, user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.brain_ingest(user, data))
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"brain ingest failed: {e}")
        raise HTTPException(500, "Brain ingestion failed")


@api.get("/brain/sources")
async def brain_sources_route(client_id: str = None, user: dict = Depends(get_current_user)):
    return _clean_value(await eng.brain_sources(user, _scoped_client(user, client_id)))


@api.delete("/brain/sources/{source_id}")
async def brain_remove_source_route(source_id: str, client_id: str = None,
                                    user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.brain_remove_source(user, source_id, _scoped_client(user, client_id)))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.post("/brain/query")
async def brain_query_route(data: BrainQueryInput, user: dict = Depends(get_current_user)):
    return _clean_value(await eng.brain_retrieve(user, data))


# ---------------- MODULE B: MARKETING MISSION PLANNER ----------------
@api.post("/missions")
async def mission_create_route(data: MissionInput, user: dict = Depends(get_current_user)):
    try:
        result = await eng.mission_create(user, data)
        result["client_id"] = _scoped_client(user, data.client_id)
        return result
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"mission create failed: {e}")
        raise HTTPException(500, "Mission planning failed")


@api.get("/missions")
async def mission_list_route(client_id: str = None, user: dict = Depends(get_current_user)):
    return _clean_value(await eng.mission_list(user, _scoped_client(user, client_id)))


@api.post("/missions/{mission_id}/approve")
async def mission_approve_route(mission_id: str, body: MissionActionInput,
                                user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.mission_approve(user, mission_id, approve=True, edits=body.edits))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.post("/missions/{mission_id}/reject")
async def mission_reject_route(mission_id: str, user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.mission_approve(user, mission_id, approve=False))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.post("/missions/{mission_id}/actions/{action_index}/approve")
async def mission_action_approve_route(mission_id: str, action_index: int,
                                       user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.mission_approve(user, mission_id, approve=True, action_index=action_index))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


# ---------------- MODULE I: LEAD INTELLIGENCE ----------------
@api.post("/leads/{lead_id}/score-ai")
async def lead_score_route(lead_id: str, user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.lead_score_explainable(user, lead_id))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.post("/leads/events")
async def lead_intent_route(data: LeadEventsInput, user: dict = Depends(get_current_user)):
    recorded = 0
    for ev in data.events:
        try:
            await eng.lead_add_intent(user, ev)
            recorded += 1
        except RuntimeError:
            pass
    return {"recorded": recorded, "total": len(data.events)}


# ---------------- MODULE M: EXPERIMENTS ----------------
@api.post("/experiments")
async def experiment_create_route(data: ExperimentInput, user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.experiment_create(user, data))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.get("/experiments")
async def experiment_list_route(client_id: str = None, user: dict = Depends(get_current_user)):
    if eng._db is None:
        return []
    tenant_key = eng._tenant_key(user, _scoped_client(user, client_id))
    docs = await eng._db.experiments.find({"tenant_key": tenant_key}).sort("created_at", -1).to_list(100)
    out = []
    for d in docs:
        d = dict(d)
        d["id"] = str(d.pop("_id"))
        variants = await eng._db.experiment_variants.find({"experiment_id": d["id"]}).to_list(20)
        for v in variants:
            v = dict(v)
            v["id"] = str(v.pop("_id"))
        d["variants"] = variants
        out.append(_clean_value(d))
    return out


@api.post("/experiments/{experiment_id}/decide")
async def experiment_decide_route(experiment_id: str, data: ExperimentDecisionInput,
                                  user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.experiment_decide(user, experiment_id, data))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


# ---------------- MODULE L: ATTRIBUTION & REVENUE ----------------
@api.post("/attribution/touch")
async def attribution_touch_route(data: AttributionTouchInput, user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.attribution_touch(user, data))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.post("/revenue")
async def revenue_record_route(data: RevenueEventInput, user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.revenue_record(user, data))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.get("/revenue")
async def revenue_list_route(client_id: str = None, user: dict = Depends(get_current_user)):
    return _clean_value(await eng.revenue_list(user, _scoped_client(user, client_id)))


@api.get("/attribution/report")
async def attribution_report_route(client_id: str = None, user: dict = Depends(get_current_user)):
    return _clean_value(await eng.attribution_report(user, _scoped_client(user, client_id)))


# ---------------- MODULE O: REVENUE INTELLIGENCE / LEARNING ----------------
@api.get("/learning")
async def learning_list_route(client_id: str = None, user: dict = Depends(get_current_user)):
    return _clean_value(await eng.learning_records(user, _scoped_client(user, client_id)))


@api.post("/learning/generate")
async def learning_generate_route(client_id: str = None, user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await eng.weekly_learning_report(user, _scoped_client(user, client_id)))
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"learning generation failed: {e}")
        raise HTTPException(500, "Learning report generation failed")


# ---------------- MODULE Q: AUTONOMY POLICY & GOVERNANCE ----------------
@api.get("/policy")
async def policy_get_route(client_id: str = None, user: dict = Depends(get_current_user)):
    return _clean_value(await eng.policy_get(user, _scoped_client(user, client_id)))


@api.post("/policy")
async def policy_set_route(data: PolicyInput, user: dict = Depends(get_current_user)):
    try:
        result = await eng.policy_set(user, data)
        result["client_id"] = _scoped_client(user, data.client_id)
        return result
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.post("/policy/kill-switch")
async def kill_switch_route(body: dict, user: dict = Depends(get_current_user)):
    active = bool(body.get("active", True))
    return _clean_value(await eng.kill_switch(user, active))


# ---------------- SCHEDULED AGENTS ----------------
@api.get("/agents/kinds")
async def agent_kinds_route(user: dict = Depends(get_current_user)):
    return {k: {"name": v["name"], "description": v["description"],
                "min_autonomy": v["policy"]} for k, v in ag.AGENT_KINDS.items()}


@api.post("/agents/schedules")
async def agent_schedule_create_route(body: dict, user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await ag.schedule_create(
            user,
            _scoped_client(user, body.get("client_id")),
            name=body.get("name", ""),
            kind=body.get("kind", ""),
            recurrence_kind=body.get("recurrence_kind", "daily"),
            recurrence_value=body.get("recurrence_value"),
            enabled=bool(body.get("enabled", True)),
            params=body.get("params") or {},
        ))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.get("/agents/schedules")
async def agent_schedule_list_route(client_id: str = None, user: dict = Depends(get_current_user)):
    return _clean_value(await ag.schedule_list(user, _scoped_client(user, client_id)))


@api.delete("/agents/schedules/{schedule_id}")
async def agent_schedule_delete_route(schedule_id: str, user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await ag.schedule_delete(user, schedule_id))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.post("/agents/schedules/{schedule_id}/toggle")
async def agent_schedule_toggle_route(schedule_id: str, body: dict,
                                      user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await ag.schedule_toggle(user, schedule_id,
                                                     bool(body.get("enabled", True))))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@api.post("/agents/schedules/{schedule_id}/run")
async def agent_schedule_run_route(schedule_id: str, user: dict = Depends(get_current_user)):
    try:
        return _clean_value(await ag.run_schedule(user, schedule_id, manual=True))
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"agent run failed: {e}")
        raise HTTPException(500, "Agent run failed")


@api.get("/agents/runs")
async def agent_runs_route(client_id: str = None, user: dict = Depends(get_current_user)):
    return _clean_value(await ag.run_list(user, _scoped_client(user, client_id)))


# ---------------- TELEMETRY & AUDIT FEEDS ----------------
@api.get("/events")
async def events_feed_route(event_type: str = None, client_id: str = None,
                            user: dict = Depends(get_current_user)):
    return _clean_value(await eng.events_feed(user, _scoped_client(user, client_id), event_type=event_type))


@api.get("/audit")
async def audit_feed_route(client_id: str = None, user: dict = Depends(get_current_user)):
    return _clean_value(await eng.audit_feed(user, _scoped_client(user, client_id)))


app.include_router(api)
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)
