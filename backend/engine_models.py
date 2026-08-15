"""Extended data models for the closed-loop revenue marketing engine.

Adds Wave-0 and core-module entities: marketing missions/plans, business brain
knowledge entries, marketing events (append-only telemetry), lead intelligence,
experiments, attribution touches, revenue events, policies, autonomous actions,
and learning records. All inputs are Pydantic v2 models consistent with models.py.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


# ---------- Business Brain / RAG ----------
class BrainIngestInput(BaseModel):
    """Ingest a URL (website crawl) or pasted document text into the tenant brain."""
    client_id: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None          # pasted text (documents, FAQs, claims)
    kind: str = "webpage"                  # webpage | document | claim | campaign_memory


class BrainQueryInput(BaseModel):
    client_id: Optional[str] = None
    query: str = Field(..., max_length=2000)
    top_k: Optional[int] = 5
    with_answer: Optional[bool] = False   # synthesize a grounded LLM answer from retrieved context


# ---------- Marketing Mission & Plan ----------
class MissionInput(BaseModel):
    client_id: Optional[str] = None
    objective: str = Field(..., max_length=4000)   # natural-language business goal
    target_market: Optional[str] = ""
    offer: Optional[str] = ""
    budget: Optional[float] = None
    currency: Optional[str] = "USD"
    geography: Optional[str] = ""
    timeline: Optional[str] = ""
    constraints: Optional[str] = ""


class MissionActionInput(BaseModel):
    edits: Optional[dict] = None


# ---------- Lead Intelligence ----------
class LeadEnrichInput(BaseModel):
    lead_id: str


class LeadIntentInput(BaseModel):
    """Record a behavioral intent signal for a lead."""
    lead_id: str
    signal_type: str = Field(..., max_length=80)   # e.g. page_visit, email_open, reply, demo_request
    details: Optional[str] = ""
    weight: Optional[float] = None


class LeadEventsInput(BaseModel):
    events: List[LeadIntentInput] = Field(default_factory=list)


# ---------- Experiments ----------
class ExperimentInput(BaseModel):
    client_id: Optional[str] = None
    name: str
    hypothesis: str
    variables: List[str]                      # e.g. ["audience", "creative"]
    primary_metric: str = "conversions"
    guardrails: Optional[str] = ""
    min_sample: int = 100
    variants: List[dict] = Field(default_factory=list)   # per-variant config dicts


class ExperimentDecisionInput(BaseModel):
    variant_winner_id: Optional[str] = None
    decision: str = "winner"                 # winner | loser | inconclusive | needs_more_data


# ---------- Attribution & Revenue ----------
class AttributionTouchInput(BaseModel):
    lead_id: Optional[str] = None
    client_id: Optional[str] = None
    campaign_id: Optional[str] = None
    channel: str
    touch_type: str = "first"                # first | interaction | last
    details: Optional[str] = ""
    value: Optional[float] = None


class RevenueEventInput(BaseModel):
    client_id: Optional[str] = None
    lead_id: Optional[str] = None
    campaign_id: Optional[str] = None
    amount: float
    currency: Optional[str] = "USD"
    stage: str = "opportunity"               # opportunity | won
    notes: Optional[str] = ""


# ---------- Autonomy Policy & Governance ----------
class PolicyInput(BaseModel):
    client_id: Optional[str] = None
    autonomy_level: str = "suggest"          # suggest | draft | approve | controlled_autopilot | full_autopilot
    max_daily_spend: Optional[float] = None
    max_budget_change_pct: Optional[float] = 25.0
    channels_allowed: Optional[List[str]] = None
    countries_allowed: Optional[List[str]] = None
    require_approval_over_amount: Optional[float] = None
    kill_switch: Optional[bool] = False


# ---------- Marketing Events (append-only telemetry) ----------
class MarketingEventInput(BaseModel):
    client_id: Optional[str] = None
    event_type: str = Field(..., max_length=80)
    actor_type: str = "human"                # human | agent | autopilot
    actor_id: Optional[str] = None
    correlation_id: Optional[str] = None
    entity_type: Optional[str] = None        # lead | campaign | mission | experiment
    entity_id: Optional[str] = None
    payload: Optional[dict] = None
