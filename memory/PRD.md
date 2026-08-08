# NEXUS — AI Marketing Engine (Autonomous Digital Marketing Platform)

## Original Problem Statement
Build an enterprise "AI Marketing Operating System" that autonomously plans, creates, executes, optimizes and measures marketing campaigns using AI agents — spanning strategy, content, social, SEO/SEM, budget, leads, sales, analytics and executive dashboards.

## User Choices
- MVP scope: Strategy Generator + Content Studio + Lead Mgmt + Lead Scoring + Sales Assistant + Analytics/Exec Dashboard (both a & b).
- Text AI: **Groq** (`llama-3.3-70b-versatile`) — user-provided GROQ_API_KEY.
- Image AI: **Gemini Nano Banana** (`gemini-3.1-flash-image-preview`) via Emergent Universal Key.
- Auth: JWT email/password.
- External channels: simulated / user-entered (per user) while AI logic is fully real.

## Architecture
- **Backend**: FastAPI (`/app/backend`) — `server.py` (routes), `auth.py` (JWT+bcrypt, httpOnly cookie), `ai.py` (Groq text/JSON + Gemini image), `models.py` (Pydantic). MongoDB via motor.
- **Frontend**: React + Tailwind + shadcn + Recharts + Phosphor icons. Swiss-brutalist dark theme (`design_guidelines.json`). AuthContext + Protected routes + sidebar shell.
- **AI is real**: strategy, content, images, lead scoring, sales assistant, social copy all call live models.

## Personas
- CMO / marketing lead: generates strategy, monitors exec dashboard.
- Marketer: creates content, schedules social, runs campaigns.
- SDR/sales: scores leads, drafts follow-ups.

## Implemented (2026-06)
- **Auth**: JWT email/password + **OTP login**. OTP channel is chosen by identifier type: **email → real Gmail SMTP code**, **phone → real Twilio Verify SMS** (start + check, no code stored locally). Wrong code → 401, unknown identifier → 404. Admin seed `admin@marketing.ai / admin123`, phone from `ADMIN_PHONE`.
- **Autopilot Cadence** (2026-06): owners set **proposals-per-day** per client workspace; admin (platform owner) sets a **global daily cap** (1–50, default 10). Daily count clamps to `[1, cap]` on read & write. Scheduler + `/proposals/generate` honor the configured count. Endpoints: `GET/POST /api/autopilot/config`. UI: steppers on the Approvals page (`cadence-stepper`, admin-only `cap-stepper`). Twilio Verify seeded as system `twilio_verify` connection from env at startup.
- AI Strategy Generator, Content Studio (text + Gemini images), Lead Management + AI scoring + stages.
- AI Sales Assistant (+ **real email send via Gmail SMTP, branded AIMarketing**).
- Campaign Manager (real CTR/CPC/CPA/ROAS/ROI), Social Manager (calendar; live LinkedIn/Meta publish when connected else simulated).
- Analytics/Executive Dashboard (real data), **currency-aware** across app.
- **Competitor & Trend Intelligence** (live web fetch + live Google News + AI).
- **Agency multi-tenant**: Client accounts, active-client selector, per-client scoping; **Client Portal Login** (client sees only their leads/campaigns/analytics; owner-only guards enforced by `_get_scoped`).
- **Settings (single credential menu)**: Business Profile + website auto-extractor + Location + Currency; encrypted Credential Vault (11 providers, Fernet at rest, masked hints).
- **Real Lead Sourcing**: Website Lead Extractor + CSV import + CRM Sync (HubSpot/Zoho when connected, else placeholder).
- **SEO-led Budget Planner** (organic ≥45%, paid supports; currency amounts).
- **Autonomous Flow** page (profile→…→reporting with live status).
- **Daily Autopilot + Human Approvals**: AI proposes campaigns; owner approves (launches real campaign) or rejects.
- AI Agents overview.
- Tested: **backend 41/41 pytest pass, frontend E2E 100%** (iterations 1–4). Multi-tenant isolation verified.

## Integration policy — NO MOCKS
Every feature is fully wired to real services. Where an external network needs YOUR developer credentials, the real API call is made once keys are saved in **Settings**; until then the endpoint returns a clear "connect in Settings" error (an *unconfigured* integration, never a fake success).
- **OTP login**: real — code delivered by real Gmail SMTP (system sender) or real Twilio SMS if connected. No on-screen dummy.
- **Email send (Sales)**: real via Gmail SMTP (AIMarketing brand).
- **Social publish**: real LinkedIn/Meta API only; 400 if not connected (no simulated "Published").
- **CRM sync (HubSpot/Zoho)**, **Google/Meta Ads**: real API calls; 400 until credentials added.
- **Competitor/Trend intel, lead scraping, CSV import, analytics**: fully real, no synthetic data.

## Backlog
- P1: Google/Meta Ads live metric auto-sync (needs API access); SEO technical audit engine (real crawl).
- P2: normalize phone formats & budget pct to 100; pagination; Recharts initial-mount size warning (cosmetic).
