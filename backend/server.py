from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import asyncio
import logging
import hashlib
import hmac
import base64
import json
import secrets
import urllib.parse
import urllib.request
from pathlib import Path
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from models import (
    StrategyInput, ContentInput, ImageInput, LeadInput, ScrapeLeadsInput, ImportLeadsInput,
    SalesAssistantInput, CampaignInput, CampaignMetricsInput,
    SocialPostInput, SchedulePostInput, CompetitorInput, TrendInput,
    ClientInput, ConnectionInput, PortalUserInput, SendEmailInput, CrmSyncInput,
    ProfileInput, ExtractProfileInput, BudgetPlanInput, PaymentCheckoutInput,
    ProposalGenerateInput, ProposalActionInput, AutopilotConfigInput, now_utc,
    SeoInput, SeoKeywordInput,
)
from engine_models import (
    BrainIngestInput, BrainQueryInput, MissionInput, MissionActionInput,
    LeadEnrichInput, LeadEventsInput, ExperimentInput, ExperimentDecisionInput,
    AttributionTouchInput, RevenueEventInput, PolicyInput,
)
import engine as eng
import agents as ag
import seo as seo_mod
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
    await db.users.create_index("google_subject", unique=True, sparse=True)
    await db.users.create_index("phone", unique=True, sparse=True)
    await db.users.create_index("tenant_id")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_tokens.create_index("token_hash", unique=True)
    await db.auth_nonces.create_index("expires_at", expireAfterSeconds=0)
    await db.auth_nonces.create_index("nonce_hash", unique=True)
    await db.auth_exchange_codes.create_index("expires_at", expireAfterSeconds=0)
    await db.auth_exchange_codes.create_index("code_hash", unique=True)
    await db.phone_otp_challenges.create_index("expires_at", expireAfterSeconds=0)
    await db.phone_otp_challenges.create_index([("phone", 1), ("intent", 1)], unique=True)
    await db.auth_rate_limits.create_index("expires_at", expireAfterSeconds=0)
    await db.auth_rate_limits.create_index([("kind", 1), ("key_hash", 1)])
    await db.payments.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.payments.create_index([("provider", 1), ("provider_reference", 1)], unique=True, sparse=True)
    await db.payment_events.create_index([("provider", 1), ("provider_event_id", 1)], unique=True)
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


def _tenant_key(user: dict) -> str:
    """Use the owner tenant for portal users and an isolated tenant key for every workspace."""
    return user.get("tenant_id") or _owner(user)


PAYMENT_PROVIDERS = {
    "stripe": {"label": "Stripe", "secret": "STRIPE_SECRET_KEY", "webhook": "STRIPE_WEBHOOK_SECRET"},
    "razorpay": {"label": "Razorpay", "secret": "RAZORPAY_KEY_SECRET", "webhook": "RAZORPAY_WEBHOOK_SECRET"},
    "paytm": {"label": "Paytm", "secret": "PAYTM_MERCHANT_KEY", "webhook": "PAYTM_MERCHANT_KEY"},
}


def _payment_plans() -> dict:
    """Load an operator-controlled plan catalogue; client requests never define charge amounts."""
    try:
        catalog = json.loads(os.environ.get("BILLING_PLANS_JSON", "{}"))
    except ValueError:
        return {}
    return catalog if isinstance(catalog, dict) else {}


def _payment_gateway_ready(provider: str, webhook: bool = False) -> bool:
    details = PAYMENT_PROVIDERS.get(provider)
    if not details:
        return False
    if not os.environ.get(details["secret"]):
        return False
    if provider == "stripe" and webhook and not os.environ.get(details["webhook"]):
        return False
    if provider == "razorpay" and (not os.environ.get("RAZORPAY_KEY_ID") or (webhook and not os.environ.get(details["webhook"]))):
        return False
    if provider == "paytm" and (not os.environ.get("PAYTM_MID") or not os.environ.get("PAYTM_WEBSITE")):
        return False
    return True


def _plan_for_checkout(code: str) -> dict:
    plan = _payment_plans().get(code)
    if not isinstance(plan, dict):
        raise HTTPException(503, "Billing plans are not configured")
    try:
        amount_minor = int(plan["amount_minor"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(503, "Billing plan price is not configured")
    currency = str(plan.get("currency", "INR")).upper()
    if amount_minor <= 0 or len(currency) != 3:
        raise HTTPException(503, "Billing plan configuration is invalid")
    return {"code": code, "name": str(plan.get("name", code)), "amount_minor": amount_minor, "currency": currency}


async def _payment_http_json(url: str, payload: dict, headers: dict) -> dict:
    encoded = json.dumps(payload).encode("utf-8")
    def send():
        request = urllib.request.Request(url, data=encoded, headers={"Content-Type": "application/json", **headers})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    try:
        return await asyncio.to_thread(send)
    except Exception as exc:
        logger.warning("Payment gateway request failed: %s", exc)
        raise HTTPException(502, "The payment gateway is temporarily unavailable")


async def _create_provider_checkout(provider: str, payment: dict, plan: dict) -> dict:
    payment_id = str(payment["_id"])
    public_url = os.environ.get("PAYMENT_PUBLIC_BASE_URL", "https://aimarket.expertaitutor.com").rstrip("/")
    if provider == "stripe":
        payload = urllib.parse.urlencode({
            "mode": "payment", "success_url": f"{public_url}/billing/success?payment_id={payment_id}",
            "cancel_url": f"{public_url}/billing/cancel?payment_id={payment_id}",
            "line_items[0][price_data][currency]": plan["currency"].lower(),
            "line_items[0][price_data][product_data][name]": plan["name"],
            "line_items[0][price_data][unit_amount]": plan["amount_minor"], "line_items[0][quantity]": 1,
            "metadata[aimarket_payment_id]": payment_id,
            "payment_intent_data[metadata][aimarket_payment_id]": payment_id,
        }).encode("utf-8")
        auth = base64.b64encode(f"{os.environ['STRIPE_SECRET_KEY']}:".encode("utf-8")).decode("ascii")
        def create_stripe():
            request = urllib.request.Request("https://api.stripe.com/v1/checkout/sessions", data=payload,
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded", "Idempotency-Key": payment_id})
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        try:
            data = await asyncio.to_thread(create_stripe)
        except Exception as exc:
            logger.warning("Stripe checkout failed: %s", exc)
            raise HTTPException(502, "Stripe checkout could not be created")
        return {"provider_reference": data["id"], "checkout_url": data["url"]}
    if provider == "razorpay":
        auth = base64.b64encode(f"{os.environ['RAZORPAY_KEY_ID']}:{os.environ['RAZORPAY_KEY_SECRET']}".encode("utf-8")).decode("ascii")
        data = await _payment_http_json("https://api.razorpay.com/v1/orders", {
            "amount": plan["amount_minor"], "currency": plan["currency"], "receipt": payment_id[-40:],
            "notes": {"aimarket_payment_id": payment_id, "tenant_id": payment["tenant_id"]},
        }, {"Authorization": f"Basic {auth}"})
        return {"provider_reference": data["id"], "checkout_url": None, "checkout_key": os.environ["RAZORPAY_KEY_ID"]}
    if provider == "paytm":
        try:
            from PaytmChecksum import PaytmChecksum
        except ImportError:
            raise HTTPException(503, "Paytm server checksum support is not installed")
        body = {"requestType": "Payment", "mid": os.environ["PAYTM_MID"], "websiteName": os.environ["PAYTM_WEBSITE"],
            "orderId": payment_id, "callbackUrl": f"{public_url}/api/payments/webhooks/paytm",
            "txnAmount": {"value": f"{plan['amount_minor'] / 100:.2f}", "currency": plan["currency"]},
            "userInfo": {"custId": payment["tenant_id"]}}
        signature = PaytmChecksum.generateSignature(json.dumps(body), os.environ["PAYTM_MERCHANT_KEY"])
        host = "https://securegw-stage.paytm.in" if os.environ.get("PAYTM_ENV", "production") == "staging" else "https://securegw.paytm.in"
        data = await _payment_http_json(f"{host}/theia/api/v1/initiateTransaction?mid={os.environ['PAYTM_MID']}&orderId={payment_id}",
            {"body": body, "head": {"signature": signature}}, {})
        result = data.get("body", {}).get("resultInfo", {})
        token = data.get("body", {}).get("txnToken")
        if result.get("resultStatus") != "S" or not token:
            raise HTTPException(502, "Paytm checkout could not be created")
        return {"provider_reference": payment_id, "checkout_url": f"{host}/theia/api/v1/showPaymentPage?mid={os.environ['PAYTM_MID']}&orderId={payment_id}&txnToken={token}"}
    raise HTTPException(400, "Unsupported payment provider")


def _verify_payment_webhook(provider: str, raw: bytes, headers, payload: dict) -> tuple[bool, str, str, bool, str | None]:
    """Verify signed raw webhook bodies and extract event metadata without trusting a client redirect."""
    if provider == "stripe":
        header = headers.get("stripe-signature", "")
        values = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
        timestamp, signature = values.get("t"), values.get("v1")
        if not timestamp or not signature or abs(now_utc().timestamp() - int(timestamp)) > 300:
            return False, "", "", False, None
        expected = hmac.new(os.environ["STRIPE_WEBHOOK_SECRET"].encode(), f"{timestamp}.".encode() + raw, hashlib.sha256).hexdigest()
        valid = hmac.compare_digest(expected, signature)
        obj = payload.get("data", {}).get("object", {})
        payment_id = obj.get("metadata", {}).get("aimarket_payment_id")
        event_type = payload.get("type", "")
        return valid, str(payload.get("id", "")), event_type, event_type in {"checkout.session.completed", "payment_intent.succeeded"} and obj.get("payment_status", "paid") == "paid", payment_id
    if provider == "razorpay":
        signature = headers.get("x-razorpay-signature", "")
        expected = hmac.new(os.environ["RAZORPAY_WEBHOOK_SECRET"].encode(), raw, hashlib.sha256).hexdigest()
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        event_type = payload.get("event", "")
        payment_id = payment.get("notes", {}).get("aimarket_payment_id")
        event_id = payload.get("id") or hashlib.sha256(f"{event_type}:".encode() + raw).hexdigest()
        return hmac.compare_digest(expected, signature), str(event_id), event_type, event_type in {"payment.captured", "order.paid"}, payment_id
    if provider == "paytm":
        try:
            from PaytmChecksum import PaytmChecksum
            checksum = payload.get("CHECKSUMHASH", "")
            values = {k: v for k, v in payload.items() if k != "CHECKSUMHASH"}
            valid = PaytmChecksum.verifySignature(values, os.environ["PAYTM_MERCHANT_KEY"], checksum)
        except Exception:
            valid = False
        txn_id, order_id = str(payload.get("TXNID", "")), payload.get("ORDERID")
        return valid, txn_id or hashlib.sha256(raw).hexdigest(), str(payload.get("STATUS", "")), payload.get("STATUS") == "TXN_SUCCESS", order_id
    return False, "", "", False, None


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


# ---------------- SEO & KEYWORD INTELLIGENCE (Module D) ----------------
@api.post("/seo/audit")
async def seo_audit(data: SeoInput, user: dict = Depends(get_current_user)):
    try:
        result = await seo_mod.crawl_tech_seo(data.url)
    except Exception as e:
        logger.error(f"seo audit failed: {e}")
        raise HTTPException(502, "Could not crawl site for technical SEO audit")
    return result


@api.post("/seo/keywords")
async def seo_keywords(data: SeoKeywordInput, user: dict = Depends(get_current_user)):
    competitors = []
    try:
        competitors = await db.competitors.find({"user_id": _owner(user)}).limit(10).to_list(10)
    except Exception:
        pass
    profile = None
    try:
        profile = await db.profiles.find_one({"user_id": _owner(user)})
    except Exception:
        pass
    product_context = (profile or {}).get("description", "")
    if not product_context:
        product_context = "No business description provided in the profile"
    try:
        result = await seo_mod.discover_keywords(data.seeds or [], data.industry or "", competitors, product_context)
    except Exception as e:
        logger.error(f"seo keywords failed: {e}")
        raise HTTPException(502, "Could not research keywords")
    return result


@api.post("/seo/briefs")
async def seo_briefs(data: SeoKeywordInput, user: dict = Depends(get_current_user)):
    profile = None
    try:
        profile = await db.profiles.find_one({"user_id": _owner(user)})
    except Exception:
        pass
    product_context = (profile or {}).get("description", "")
    keywords = data.keywords if isinstance(data.keywords, list) else []
    try:
        result = await seo_mod.keyword_briefs(keywords, data.industry or "", product_context)
    except Exception as e:
        logger.error(f"seo briefs failed: {e}")
        raise HTTPException(502, "Could not generate content briefs")
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


# ---------------- PAYMENTS (tenant-scoped; provider confirmation only) ----------------
@api.get("/payments/gateways")
async def payment_gateways(user: dict = Depends(get_current_user)):
    _require_owner(user)
    return [{"provider": provider, "label": config["label"], "checkout_ready": _payment_gateway_ready(provider),
             "webhook_ready": _payment_gateway_ready(provider, webhook=True), "plans_configured": bool(_payment_plans()),
             "mode": "configuration_pending" if not _payment_gateway_ready(provider) else "ready"}
            for provider, config in PAYMENT_PROVIDERS.items()]


@api.get("/payments/plans")
async def payment_plans(user: dict = Depends(get_current_user)):
    _require_owner(user)
    plans = []
    for code in _payment_plans():
        try:
            plans.append(_plan_for_checkout(code))
        except HTTPException:
            continue
    return plans


@api.get("/payments")
async def list_payments(client_id: str = None, user: dict = Depends(get_current_user)):
    _require_owner(user)
    query = {"tenant_id": _tenant_key(user)}
    scoped = _scoped_client(user, client_id)
    if scoped:
        query["client_id"] = scoped
    docs = await db.payments.find(query).sort("created_at", -1).to_list(200)
    return [_serialize(doc) for doc in docs]


@api.post("/payments/checkout")
async def create_payment_checkout(data: PaymentCheckoutInput, user: dict = Depends(get_current_user)):
    _require_owner(user)
    provider = data.provider
    if not _payment_gateway_ready(provider):
        raise HTTPException(503, f"{PAYMENT_PROVIDERS[provider]['label']} is awaiting secure platform configuration")
    plan = _plan_for_checkout(data.plan_code)
    client_id = _scoped_client(user, data.client_id)
    payment = {"tenant_id": _tenant_key(user), "owner_user_id": _owner(user), "client_id": client_id, "provider": provider,
               "plan_code": plan["code"], "plan_name": plan["name"], "amount_minor": plan["amount_minor"], "currency": plan["currency"],
               "status": "checkout_created", "created_at": now_utc(), "updated_at": now_utc()}
    result = await db.payments.insert_one(payment)
    payment["_id"] = result.inserted_id
    try:
        checkout = await _create_provider_checkout(provider, payment, plan)
    except HTTPException:
        await db.payments.update_one({"_id": result.inserted_id}, {"$set": {"status": "checkout_failed", "updated_at": now_utc()}})
        raise
    await db.payments.update_one({"_id": result.inserted_id}, {"$set": {**checkout, "updated_at": now_utc()}})
    return {"payment_id": str(result.inserted_id), "provider": provider, "status": "checkout_created", **checkout}


@api.post("/payments/webhooks/{provider}")
async def payment_webhook(provider: str, request: Request):
    if provider not in PAYMENT_PROVIDERS or not _payment_gateway_ready(provider, webhook=True):
        raise HTTPException(503, "Payment webhook is not configured")
    raw = await request.body()
    try:
        payload = urllib.parse.parse_qs(raw.decode("utf-8")) if provider == "paytm" else json.loads(raw)
        if provider == "paytm":
            payload = {key: values[-1] for key, values in payload.items()}
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(400, "Invalid payment webhook payload")
    valid, event_id, event_type, paid, payment_id = _verify_payment_webhook(provider, raw, request.headers, payload)
    if not valid or not event_id:
        raise HTTPException(400, "Invalid payment webhook signature")
    try:
        await db.payment_events.insert_one({"provider": provider, "provider_event_id": event_id, "event_type": event_type,
                                              "payload_hash": hashlib.sha256(raw).hexdigest(), "received_at": now_utc()})
    except Exception as exc:
        if exc.__class__.__name__ == "DuplicateKeyError":
            return {"received": True, "duplicate": True}
        raise
    if paid and payment_id:
        try:
            payment = await db.payments.find_one({"_id": ObjectId(payment_id), "provider": provider})
        except Exception:
            payment = None
        if payment:
            await db.payments.update_one({"_id": payment["_id"], "status": {"$ne": "paid"}}, {"$set": {"status": "paid", "paid_at": now_utc(), "updated_at": now_utc(), "provider_event_id": event_id}})
    return {"received": True}

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
        "tenant_id": user.get("tenant_id") or _owner(user),
        "client_id": cid,
        "token_version": 0,
        "password_change_required": False,
        "created_at": now_utc(),
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


# ---------------- SECURE PROVIDER OAUTH ----------------
# OAuth client secrets remain in server environment variables only. The mobile
# client receives an official provider consent URL and never handles passwords,
# two-factor codes, client secrets, refresh tokens, or access tokens.
OAUTH_PROVIDERS = {
    "google_ads": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id_env": "GOOGLE_ADS_OAUTH_CLIENT_ID",
        "client_secret_env": "GOOGLE_ADS_OAUTH_CLIENT_SECRET",
        "scopes": ["https://www.googleapis.com/auth/adwords"],
    },
    "linkedin": {
        "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "client_id_env": "LINKEDIN_OAUTH_CLIENT_ID",
        "client_secret_env": "LINKEDIN_OAUTH_CLIENT_SECRET",
        "scopes": ["openid", "profile"],
    },
    "meta": {
        "authorize_url": "https://www.facebook.com/v20.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
        "client_id_env": "META_OAUTH_APP_ID",
        "client_secret_env": "META_OAUTH_APP_SECRET",
        "scopes": ["pages_show_list", "pages_read_engagement"],
    },
    "meta_ads": {
        "authorize_url": "https://www.facebook.com/v20.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
        "client_id_env": "META_OAUTH_APP_ID",
        "client_secret_env": "META_OAUTH_APP_SECRET",
        "scopes": ["ads_read"],
    },
}


def _oauth_redirect_uri(provider: str) -> str:
    base = os.environ.get("OAUTH_CALLBACK_BASE_URL", "https://aimarket.expertaitutor.com/api/connections/oauth")
    return f"{base.rstrip('/')}/{provider}/callback"


def _oauth_config(provider: str) -> dict:
    config = OAUTH_PROVIDERS.get(provider)
    if not config:
        raise HTTPException(400, "OAuth is not supported for this provider")
    client_id = os.environ.get(config["client_id_env"])
    client_secret = os.environ.get(config["client_secret_env"])
    if not client_id or not client_secret:
        raise HTTPException(503, f"{provider} OAuth is not configured by the platform owner")
    return {**config, "client_id": client_id, "client_secret": client_secret}


async def _oauth_token_exchange(token_url: str, payload: dict) -> dict:
    """Perform the authorization-code exchange server-to-server only."""
    def exchange():
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(token_url, data=encoded, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    try:
        return await asyncio.to_thread(exchange)
    except Exception as exc:
        logger.warning("OAuth token exchange failed: %s", exc)
        raise HTTPException(502, "The provider token exchange failed")


@api.post("/connections/oauth/{provider}/start")
async def oauth_start(provider: str, body: dict, user: dict = Depends(get_current_user)):
    _require_owner(user)
    config = _oauth_config(provider)
    role = body.get("connection_role", "customer")
    if role not in {"customer", "owner_managed"}:
        raise HTTPException(400, "Invalid connection role")
    if role == "owner_managed" and not body.get("authorization_confirmed"):
        raise HTTPException(400, "Owner-managed connections require explicit client authorization confirmation")
    client_id = _scoped_client(user, body.get("client_id"))
    state = secrets.token_urlsafe(32)
    now = now_utc()
    await db.oauth_states.insert_one({
        "state_hash": hashlib.sha256(state.encode("utf-8")).hexdigest(),
        "user_id": _owner(user), "client_id": client_id, "provider": provider,
        "connection_role": role, "authorization_confirmed": bool(body.get("authorization_confirmed")),
        "created_at": now.isoformat(), "expires_ts": now.timestamp() + 600, "used_at": None,
    })
    params = {
        "response_type": "code", "client_id": config["client_id"],
        "redirect_uri": _oauth_redirect_uri(provider), "scope": " ".join(config["scopes"]),
        "state": state,
    }
    return {"provider": provider, "authorization_url": f"{config['authorize_url']}?{urllib.parse.urlencode(params)}",
            "redirect_uri": _oauth_redirect_uri(provider), "expires_in_seconds": 600,
            "message": "Complete consent only on the provider's official authorization page."}


@api.get("/connections/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request, code: str = None, state: str = None, error: str = None):
    if error:
        return {"connected": False, "provider": provider, "message": "Provider consent was not completed", "provider_error": error}
    if not code or not state:
        raise HTTPException(400, "Missing OAuth authorization code or state")
    config = _oauth_config(provider)
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    record = await db.oauth_states.find_one({"state_hash": state_hash, "provider": provider})
    if not record or record.get("used_at") or record.get("expires_ts", 0) < now_utc().timestamp():
        raise HTTPException(400, "OAuth state is invalid or expired")
    await db.oauth_states.update_one({"_id": record["_id"], "used_at": None}, {"$set": {"used_at": now_utc().isoformat()}})
    token = await _oauth_token_exchange(config["token_url"], {
        "grant_type": "authorization_code", "code": code, "redirect_uri": _oauth_redirect_uri(provider),
        "client_id": config["client_id"], "client_secret": config["client_secret"],
    })
    if not token.get("access_token"):
        raise HTTPException(502, "Provider returned no access token")
    encrypted = {key: ss.encrypt(str(value)) for key, value in token.items() if key in {"access_token", "refresh_token", "id_token", "token_type", "scope", "expires_in"} and value is not None}
    doc = {
        "user_id": record["user_id"], "client_id": record.get("client_id"), "provider": provider,
        "credentials": encrypted, "auth_type": "oauth_authorization_code",
        "connection_role": record.get("connection_role"), "authorization_confirmed": record.get("authorization_confirmed", False),
        "token_obtained_at": now_utc().isoformat(), "updated_at": now_utc().isoformat(),
    }
    await db.connections.update_one({"user_id": record["user_id"], "client_id": record.get("client_id"), "provider": provider}, {"$set": doc}, upsert=True)
    await db.audit_log.insert_one({"user_id": record["user_id"], "event": "OAuthConnectionCreated", "provider": provider,
                                    "client_id": record.get("client_id"), "created_at": now_utc().isoformat(),
                                    "request_path": str(request.url.path)})
    return {"connected": True, "provider": provider, "message": "Connection authorized. You can return to AiMarket."}


@api.post("/notifications/devices")
async def register_notification_device(body: dict, user: dict = Depends(get_current_user)):
    token = str(body.get("expo_push_token", "")).strip()
    if not token:
        raise HTTPException(400, "An Expo push token is required")
    await db.notification_devices.update_one(
        {"user_id": _owner(user), "token_hash": hashlib.sha256(token.encode()).hexdigest()},
        {"$set": {"user_id": _owner(user), "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                  "encrypted_token": ss.encrypt(token), "platform": body.get("platform", "unknown"),
                  "updated_at": now_utc().isoformat()}}, upsert=True,
    )
    return {"registered": True}


async def _send_expo_approval_notifications(user_id: str, title: str, body: str, data: dict) -> int:
    """Deliver budget-approval alerts to registered Expo devices without exposing tokens."""
    devices = await db.notification_devices.find({"user_id": user_id}).to_list(50)
    delivered = 0
    for device in devices:
        token = ss.decrypt(device.get("encrypted_token", ""))
        if not token:
            continue
        payload = json.dumps({"to": token, "title": title, "body": body, "sound": "default", "data": data}).encode("utf-8")
        def send():
            request = urllib.request.Request("https://exp.host/--/api/v2/push/send", data=payload,
                                             headers={"Content-Type": "application/json", "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=12) as response:
                return response.status
        try:
            status = await asyncio.to_thread(send)
            delivered += 1 if 200 <= status < 300 else 0
        except Exception as exc:
            logger.warning("Expo approval notification failed for device %s: %s", device.get("_id"), exc)
    return delivered


# ---------------- PROVIDER-SPECIFIC BUDGET APPROVALS ----------------
BUDGET_PROVIDER_GUARDRAILS = {
    "google_ads": {"max_test_change_pct": 20.0, "requires_connected_provider": True},
    "meta_ads": {"max_test_change_pct": 15.0, "requires_connected_provider": True},
    "linkedin_ads": {"max_test_change_pct": 10.0, "requires_connected_provider": True},
}


@api.post("/budget/approval-requests")
async def create_budget_approval_request(body: dict, user: dict = Depends(get_current_user)):
    _require_owner(user)
    provider = str(body.get("provider", ""))
    rules = BUDGET_PROVIDER_GUARDRAILS.get(provider)
    if not rules:
        raise HTTPException(400, "Budget approvals are supported for Google Ads, Meta Ads, and LinkedIn Ads")
    client_id = _scoped_client(user, body.get("client_id"))
    try:
        current = float(body.get("current_daily_budget", 0)); proposed = float(body.get("proposed_daily_budget", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "Current and proposed daily budgets must be valid numbers")
    if current < 0 or proposed <= 0:
        raise HTTPException(400, "Budget values must be positive")
    policy = await eng.policy_get(user, client_id)
    change_pct = abs(proposed - current) / current * 100 if current else 100.0
    blockers = []
    if policy.get("kill_switch"):
        blockers.append("The global kill switch is active")
    if policy.get("max_daily_spend") is not None and proposed > float(policy["max_daily_spend"]):
        blockers.append("Proposed daily spend exceeds the policy cap")
    max_change = min(float(policy.get("max_budget_change_pct") or 25.0), rules["max_test_change_pct"])
    if change_pct > max_change:
        blockers.append(f"Change exceeds the {max_change:.0f}% provider test cap")
    connection = await db.connections.find_one({"user_id": _owner(user), "client_id": client_id, "provider": provider})
    if rules["requires_connected_provider"] and not connection:
        blockers.append("Official provider OAuth connection is required before execution")
    request_doc = {
        "user_id": _owner(user), "client_id": client_id, "provider": provider,
        "current_daily_budget": current, "proposed_daily_budget": proposed, "change_pct": round(change_pct, 2),
        "rationale": str(body.get("rationale", "")), "evidence": body.get("evidence", {}),
        "policy_snapshot": {"max_daily_spend": policy.get("max_daily_spend"), "max_budget_change_pct": policy.get("max_budget_change_pct"), "kill_switch": policy.get("kill_switch")},
        "status": "Blocked" if blockers else "PendingApproval", "blockers": blockers,
        "execution_mode": "manual_provider_confirmation", "created_at": now_utc().isoformat(),
    }
    result = await db.budget_approval_requests.insert_one(request_doc)
    request_doc["_id"] = result.inserted_id
    devices = await db.notification_devices.count_documents({"user_id": _owner(user)})
    delivered = await _send_expo_approval_notifications(
        _owner(user), "Budget approval required" if not blockers else "Budget change blocked",
        f"{provider.replace('_', ' ').title()}: {change_pct:.1f}% daily budget change is {request_doc['status'].lower()}.",
        {"kind": "budget_approval", "budget_request_id": str(result.inserted_id), "status": request_doc["status"]},
    )
    await db.notification_events.insert_one({"user_id": _owner(user), "kind": "budget_approval", "budget_request_id": str(result.inserted_id),
                                             "delivery_status": "sent" if delivered else ("failed" if devices else "no_registered_device"), "created_at": now_utc().isoformat()})
    return _serialize(request_doc)


@api.get("/budget/approval-requests")
async def list_budget_approval_requests(client_id: str = None, user: dict = Depends(get_current_user)):
    cid = _scoped_client(user, client_id)
    query = {"user_id": _owner(user)}
    if cid:
        query["client_id"] = cid
    docs = await db.budget_approval_requests.find(query).sort("created_at", -1).to_list(100)
    return [_serialize(doc) for doc in docs]


@api.post("/budget/approval-requests/{request_id}/decision")
async def decide_budget_approval_request(request_id: str, body: dict, user: dict = Depends(get_current_user)):
    _require_owner(user)
    request_doc = await _get_scoped(db.budget_approval_requests, request_id, user)
    decision = body.get("decision")
    if decision not in {"approve", "reject"}:
        raise HTTPException(400, "Decision must be approve or reject")
    if request_doc.get("status") != "PendingApproval":
        raise HTTPException(400, "Only pending requests can be decided")
    status = "ApprovedForManualExecution" if decision == "approve" else "Rejected"
    await db.budget_approval_requests.update_one({"_id": request_doc["_id"]}, {"$set": {"status": status, "decision_note": str(body.get("note", "")), "decided_at": now_utc().isoformat(), "decided_by": str(user["_id"])}})
    delivered = await _send_expo_approval_notifications(
        _owner(user), "Budget request approved" if decision == "approve" else "Budget request rejected",
        "No provider budget was changed automatically. Review the manual provider-side confirmation before execution.",
        {"kind": "budget_approval_decision", "budget_request_id": request_id, "status": status},
    )
    await db.notification_events.insert_one({"user_id": _owner(user), "kind": "budget_approval_decision", "budget_request_id": request_id,
                                             "delivery_status": "sent" if delivered else "no_registered_device", "created_at": now_utc().isoformat()})
    return {"id": request_id, "status": status, "message": "No provider budget was changed automatically; complete the provider-side confirmation after review."}


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
