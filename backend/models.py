from datetime import datetime, timezone
from typing import Annotated, Any, Optional, Literal
from bson import ObjectId
from pydantic import BaseModel, Field, BeforeValidator, ConfigDict, EmailStr


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
        return cls(**doc) if doc else None

    def to_mongo(self) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        data.pop("_id", None)
        return data


# ---------- Auth ----------
class RegisterInput(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    phone: Optional[str] = ""
    password: Optional[str] = None
    use_generated_password: bool = True


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequestInput(BaseModel):
    email: EmailStr
    delivery: Literal["link", "temporary"] = "link"


class PasswordResetConfirmInput(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class PasswordChangeInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class PaymentCheckoutInput(BaseModel):
    provider: Literal["stripe", "razorpay", "paytm"]
    plan_code: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    client_id: Optional[str] = None


class OtpRequestInput(BaseModel):
    identifier: str


class OtpVerifyInput(BaseModel):
    identifier: str
    code: str


class GoogleIdentityInput(BaseModel):
    id_token: str = Field(min_length=100, max_length=16384)
    nonce: str = Field(min_length=16, max_length=128)


class GoogleExchangeInput(BaseModel):
    code: str = Field(min_length=32, max_length=256)


class PhoneOtpRequestInput(BaseModel):
    phone: str = Field(min_length=8, max_length=32)
    consent: bool
    intent: Literal["login", "signup"] = "login"
    name: str = Field(default="", max_length=120)


class PhoneOtpVerifyInput(BaseModel):
    phone: str = Field(min_length=8, max_length=32)
    code: str = Field(min_length=4, max_length=12)
    intent: Literal["login", "signup"] = "login"


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
    action: str


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


# ---------- SEO & Keyword Intelligence ----------
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


# ---------- Connections ----------
class ConnectionInput(BaseModel):
    provider: str
    client_id: Optional[str] = None
    credentials: dict = {}


# ---------- Portal / Live integrations ----------
class PortalUserInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    name: Optional[str] = ""


class SendEmailInput(BaseModel):
    lead_id: str
    subject: str
    message: str


class CrmSyncInput(BaseModel):
    provider: str
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
    daily_proposals: Optional[int] = None
    cap: Optional[int] = None


class ProposalGenerateInput(BaseModel):
    client_id: Optional[str] = None


class ProposalActionInput(BaseModel):
    edits: Optional[dict] = None


class ExtractProfileInput(BaseModel):
    url: str


# ---------- Budget Planner ----------
class BudgetPlanInput(BaseModel):
    total_budget: float
    period: str = "Monthly"
    primary_goal: str = "Generate qualified leads"
    notes: Optional[str] = ""
    client_id: Optional[str] = None
