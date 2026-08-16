from datetime import datetime, timezone
from typing import Annotated, Any, Optional, List
from bson import ObjectId
from pydantic import BaseModel, Field, BeforeValidator, ConfigDict


def _validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    return str(v)


PyObjectId = Annotated[str, BeforeValidator(_validate_object_id)]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: dict):
        if not doc:
            return None
        return cls(**doc)

    def to_mongo(self) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        data.pop("_id", None)
        return data


# ---------- Auth ----------
class RegisterInput(BaseModel):
    email: str
    password: str
    name: str
    phone: Optional[str] = ""


class LoginInput(BaseModel):
    email: str
    password: str


class OtpRequestInput(BaseModel):
    identifier: str  # email or phone


class OtpVerifyInput(BaseModel):
    identifier: str
    code: str


# ---------- Strategy ----------
class StrategyInput(BaseModel):
    industry: str
    product: str
    competitors: Optional[str] = ""
    budget: str
    geography: str
    goals: str


# ---------- Content ----------
class ContentInput(BaseModel):
    content_type: str
    topic: str
    tone: Optional[str] = "professional"
    language: Optional[str] = "English"
    keywords: Optional[str] = ""


class ImageInput(BaseModel):
    prompt: str
    style: Optional[str] = "modern marketing poster"


# ---------- Leads ----------
class LeadInput(BaseModel):
    name: str
    email: str
    company: str
    role: Optional[str] = ""
    industry: Optional[str] = ""
    company_size: Optional[str] = ""
    budget: Optional[str] = ""
    source: Optional[str] = "Website"
    notes: Optional[str] = ""
    client_id: Optional[str] = None


class ScrapeLeadsInput(BaseModel):
    domains: str
    client_id: Optional[str] = None


class ImportLeadsInput(BaseModel):
    csv_text: str
    client_id: Optional[str] = None


class SalesAssistantInput(BaseModel):
    lead_id: str
    action: str  # follow_up_email, whatsapp, objection_handling, summary


# ---------- Campaigns ----------
class CampaignInput(BaseModel):
    name: str
    channel: str
    objective: str
    budget: float
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    revenue: float = 0.0
    client_id: Optional[str] = None


class CampaignMetricsInput(BaseModel):
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    revenue: float = 0.0


# ---------- Social ----------
class SocialPostInput(BaseModel):
    platform: str
    topic: str
    tone: Optional[str] = "engaging"


class SchedulePostInput(BaseModel):
    platform: str
    content: str
    scheduled_time: str


# ---------- Competitor Intelligence ----------
class CompetitorInput(BaseModel):
    name: str
    url: str


class TrendInput(BaseModel):
    industry: str


# ---------- SEO & Keyword Intelligence (Module D) ----------
class SeoInput(BaseModel):
    url: str


class SeoKeywordInput(BaseModel):
    seeds: list = []
    industry: str = ""
    keywords: list = []


# ---------- Clients (Agency multi-tenant) ----------
class ClientInput(BaseModel):
    name: str
    industry: Optional[str] = ""
    website: Optional[str] = ""
    contact_email: Optional[str] = ""
    notes: Optional[str] = ""


# ---------- Connections (encrypted credential placeholders) ----------
class ConnectionInput(BaseModel):
    provider: str
    client_id: Optional[str] = None  # which customer account this belongs to
    credentials: dict = {}


# ---------- Portal / Live integrations ----------
class PortalUserInput(BaseModel):
    email: str
    password: str
    name: Optional[str] = ""


class SendEmailInput(BaseModel):
    lead_id: str
    subject: str
    message: str


class CrmSyncInput(BaseModel):
    provider: str  # hubspot | zoho
    client_id: Optional[str] = None


# ---------- Business Profile / Currency ----------
class ProfileInput(BaseModel):
    company_name: Optional[str] = ""
    description: Optional[str] = ""
    industry: Optional[str] = ""
    website: Optional[str] = ""
    country: Optional[str] = "United States"
    currency: Optional[str] = "USD"
    autopilot: Optional[bool] = False
    daily_proposals: Optional[int] = 3
    client_id: Optional[str] = None


class AutopilotConfigInput(BaseModel):
    daily_proposals: Optional[int] = None  # owner: proposals per day for this scope
    cap: Optional[int] = None              # admin only: global max per day
    client_id: Optional[str] = None


class ProposalGenerateInput(BaseModel):
    client_id: Optional[str] = None


class ProposalActionInput(BaseModel):
    edits: Optional[dict] = None


class ExtractProfileInput(BaseModel):
    url: str


# ---------- Budget Planner (SEO-led) ----------
class BudgetPlanInput(BaseModel):
    total_budget: float
    period: str = "Monthly"          # Monthly | Quarterly | Annual
    primary_goal: str = "Generate qualified leads"
    notes: Optional[str] = ""
    client_id: Optional[str] = None
