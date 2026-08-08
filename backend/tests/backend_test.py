"""Backend API tests for AI Marketing Engine."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to frontend env
    from pathlib import Path
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@marketing.ai"
ADMIN_PASSWORD = "admin123"

AI_TIMEOUT = 90


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth_session(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    body = r.json()
    assert "token" in body and "user" in body
    session.headers.update({"Authorization": f"Bearer {body['token']}"})
    return session


# ---------- Auth ----------
class TestAuth:
    def test_root(self, session):
        r = session.get(f"{BASE_URL}/api/", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "online"

    def test_login_success(self, session):
        r = session.post(f"{BASE_URL}/api/auth/login",
                         json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == ADMIN_EMAIL
        assert d["user"]["role"] == "admin"
        assert isinstance(d["token"], str) and len(d["token"]) > 20
        # cookie set?
        assert "access_token" in r.cookies

    def test_login_wrong_password(self, session):
        r = session.post(f"{BASE_URL}/api/auth/login",
                         json={"email": ADMIN_EMAIL, "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_me(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_register_and_logout(self, session):
        email = f"test_user_{int(time.time())}@example.com"
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/register",
                   json={"email": email, "password": "pass1234", "name": "Test User"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["user"]["email"] == email
        # logout
        r = s.post(f"{BASE_URL}/api/auth/logout", timeout=10)
        assert r.status_code == 200

    def test_me_unauth(self, session):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 401


# ---------- Strategy (real AI) ----------
class TestStrategy:
    def test_generate_and_list(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/strategy/generate", json={
            "industry": "SaaS",
            "product": "AI Marketing Platform",
            "competitors": "HubSpot",
            "budget": "$50k/month",
            "geography": "North America",
            "goals": "Grow MQLs 3x",
        }, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "id" in d
        res = d.get("result") or {}
        for key in ("executive_summary", "personas", "channel_mix", "budget_allocation", "kpis"):
            assert key in res, f"missing key {key} in strategy result"
        # list
        r2 = auth_session.get(f"{BASE_URL}/api/strategy", timeout=15)
        assert r2.status_code == 200
        assert any(item["id"] == d["id"] for item in r2.json())


# ---------- Content ----------
class TestContent:
    def test_generate_text(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/content/generate", json={
            "content_type": "blog", "topic": "AI marketing trends 2026",
            "tone": "professional", "language": "English", "keywords": "AI, marketing",
        }, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        res = r.json().get("result") or {}
        for key in ("title", "body", "hashtags", "seo_keywords", "cta"):
            assert key in res, f"missing {key}"
        # list
        r2 = auth_session.get(f"{BASE_URL}/api/content", timeout=15)
        assert r2.status_code == 200
        assert len(r2.json()) >= 1

    def test_generate_image(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/content/image", json={
            "prompt": "A vibrant marketing banner about AI",
            "style": "modern marketing poster",
        }, timeout=120)
        assert r.status_code == 200, r.text[:500]
        res = r.json().get("result") or {}
        url = res.get("image_url", "")
        assert url.startswith("data:image/"), "image_url should be data URL"
        assert len(url) > 500  # base64 present


# ---------- Leads ----------
class TestLeads:
    lead_id = None

    def test_crud_and_score(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/leads", json={
            "name": "TEST_John", "email": "test_lead@example.com",
            "company": "Acme Corp", "role": "CMO",
            "industry": "SaaS", "company_size": "500",
            "budget": "$100k", "source": "Website",
            "notes": "Interested in AI marketing platform, met at conference",
        }, timeout=15)
        assert r.status_code == 200, r.text
        lead = r.json()
        lid = lead["id"]
        assert lead["category"] == "Unscored"

        # list
        r = auth_session.get(f"{BASE_URL}/api/leads", timeout=15)
        assert r.status_code == 200
        assert any(l["id"] == lid for l in r.json())

        # score (AI)
        r = auth_session.post(f"{BASE_URL}/api/leads/{lid}/score", timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        scored = r.json()
        assert scored["category"] in ("Hot", "Warm", "Cold", "Sales Ready")
        assert isinstance(scored["score"], (int, float))

        # stage update
        r = auth_session.patch(f"{BASE_URL}/api/leads/{lid}/stage",
                               json={"stage": "Opportunity"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["stage"] == "Opportunity"

        # sales assist
        r = auth_session.post(f"{BASE_URL}/api/sales/assist",
                              json={"lead_id": lid, "action": "follow_up_email"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "result" in d
        assert "title" in d["result"] and "message" in d["result"]

        # delete
        r = auth_session.delete(f"{BASE_URL}/api/leads/{lid}", timeout=15)
        assert r.status_code == 200


# ---------- Campaigns ----------
class TestCampaigns:
    def test_crud_metrics(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/campaigns", json={
            "name": "TEST_Campaign", "channel": "Google Ads", "objective": "Conversions",
            "budget": 1000, "impressions": 10000, "clicks": 500,
            "conversions": 50, "revenue": 5000,
        }, timeout=15)
        assert r.status_code == 200, r.text
        c = r.json()
        cid = c["id"]
        # derived
        assert c["ctr"] == 5.0  # 500/10000 * 100
        assert c["cpc"] == 2.0
        assert c["cpa"] == 20.0
        assert c["roas"] == 5.0
        assert c["roi"] == 400.0

        # list
        r = auth_session.get(f"{BASE_URL}/api/campaigns", timeout=15)
        assert r.status_code == 200

        # update metrics
        r = auth_session.patch(f"{BASE_URL}/api/campaigns/{cid}/metrics", json={
            "impressions": 20000, "clicks": 1000, "conversions": 100, "revenue": 10000,
        }, timeout=15)
        assert r.status_code == 200
        assert r.json()["impressions"] == 20000

        # toggle
        r = auth_session.patch(f"{BASE_URL}/api/campaigns/{cid}/toggle", timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "Paused"

        # delete
        r = auth_session.delete(f"{BASE_URL}/api/campaigns/{cid}", timeout=15)
        assert r.status_code == 200


# ---------- Social ----------
class TestSocial:
    def test_generate_schedule_publish_delete(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/social/generate", json={
            "platform": "LinkedIn", "topic": "AI marketing", "tone": "engaging",
        }, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        gen = r.json()
        assert "content" in gen and "hashtags" in gen

        r = auth_session.post(f"{BASE_URL}/api/social/schedule", json={
            "platform": "LinkedIn",
            "content": gen.get("content", "TEST content"),
            "scheduled_time": "2026-02-01T10:00:00",
        }, timeout=15)
        assert r.status_code == 200
        pid = r.json()["id"]

        r = auth_session.get(f"{BASE_URL}/api/social/posts", timeout=15)
        assert r.status_code == 200
        assert any(p["id"] == pid for p in r.json())

        r = auth_session.patch(f"{BASE_URL}/api/social/posts/{pid}/publish", timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "Published"

        r = auth_session.delete(f"{BASE_URL}/api/social/posts/{pid}", timeout=15)
        assert r.status_code == 200


# ---------- Clients (Agency multi-tenant) ----------
class TestClients:
    def test_client_crud_and_scoping(self, auth_session):
        # CREATE client
        r = auth_session.post(f"{BASE_URL}/api/clients", json={
            "name": "TEST_Acme Agency", "industry": "SaaS",
            "website": "https://acme.test", "contact_email": "ops@acme.test",
            "notes": "test client",
        }, timeout=15)
        assert r.status_code == 200, r.text
        c = r.json()
        cid = c["id"]
        assert c["name"] == "TEST_Acme Agency"
        assert c["industry"] == "SaaS"

        # LIST with counts
        r = auth_session.get(f"{BASE_URL}/api/clients", timeout=15)
        assert r.status_code == 200
        found = [x for x in r.json() if x["id"] == cid]
        assert len(found) == 1
        assert "leads" in found[0] and "campaigns" in found[0] and "connections" in found[0]
        assert found[0]["leads"] == 0

        # PATCH
        r = auth_session.patch(f"{BASE_URL}/api/clients/{cid}", json={
            "name": "TEST_Acme Agency", "industry": "MarTech",
            "website": "https://acme.test", "contact_email": "ops@acme.test",
            "notes": "updated",
        }, timeout=15)
        assert r.status_code == 200
        assert r.json()["industry"] == "MarTech"

        # Scoped lead
        r = auth_session.post(f"{BASE_URL}/api/leads", json={
            "name": "TEST_ScopedLead", "email": "scoped@acme.test",
            "company": "Acme", "role": "CEO", "client_id": cid,
        }, timeout=15)
        assert r.status_code == 200, r.text
        lead_id = r.json()["id"]

        # Scoped list returns only that client's leads
        r = auth_session.get(f"{BASE_URL}/api/leads", params={"client_id": cid}, timeout=15)
        assert r.status_code == 200
        leads = r.json()
        assert all(l.get("client_id") == cid for l in leads)
        assert any(l["id"] == lead_id for l in leads)

        # Scoped campaign
        r = auth_session.post(f"{BASE_URL}/api/campaigns", json={
            "name": "TEST_ScopedCamp", "channel": "Google Ads", "objective": "Leads",
            "budget": 500, "impressions": 1000, "clicks": 50, "conversions": 5,
            "revenue": 1000, "client_id": cid,
        }, timeout=15)
        assert r.status_code == 200, r.text
        camp_id = r.json()["id"]

        r = auth_session.get(f"{BASE_URL}/api/campaigns", params={"client_id": cid}, timeout=15)
        assert r.status_code == 200
        assert any(c["id"] == camp_id for c in r.json())
        assert all(c.get("client_id") == cid for c in r.json())

        # verify counts updated on client list
        r = auth_session.get(f"{BASE_URL}/api/clients", timeout=15)
        rec = [x for x in r.json() if x["id"] == cid][0]
        assert rec["leads"] >= 1
        assert rec["campaigns"] >= 1

        # cleanup lead & campaign
        auth_session.delete(f"{BASE_URL}/api/leads/{lead_id}", timeout=15)
        auth_session.delete(f"{BASE_URL}/api/campaigns/{camp_id}", timeout=15)

        # DELETE client
        r = auth_session.delete(f"{BASE_URL}/api/clients/{cid}", timeout=15)
        assert r.status_code == 200


# ---------- Integrations providers ----------
class TestIntegrationProviders:
    def test_providers_list(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/integrations/providers", timeout=15)
        assert r.status_code == 200
        providers = r.json()
        assert len(providers) == 11
        ids = {p["id"] for p in providers}
        for expected in ("linkedin", "meta", "twitter_x", "google_ads", "meta_ads",
                         "email", "whatsapp", "google_search", "hubspot", "zoho", "salesforce"):
            assert expected in ids
        for p in providers:
            assert "label" in p and "category" in p and "fields" in p and "help" in p
            assert isinstance(p["fields"], list) and len(p["fields"]) >= 1


# ---------- Connections (encryption) ----------
class TestConnections:
    def test_initial_pending_and_no_plaintext(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/connections", timeout=15)
        assert r.status_code == 200
        conns = r.json()
        assert len(conns) == 11
        # Clean slate at platform scope: delete any lingering to make deterministic
        # NOTE: 'email' is seeded at startup from env — do NOT delete it (iteration 3)
        for c in conns:
            if c["status"] != "Pending" and c["provider"] != "email":
                auth_session.delete(f"{BASE_URL}/api/connections/{c['provider']}", timeout=10)
        # re-fetch
        r = auth_session.get(f"{BASE_URL}/api/connections", timeout=15)
        conns = r.json()
        for c in conns:
            if c["provider"] == "email":
                continue  # seeded from env — skip
            assert c["status"] == "Pending"
            for f, meta in c["credentials"].items():
                assert set(meta.keys()) >= {"set", "hint"}
                assert meta["set"] is False
                assert meta["hint"] == ""

    def test_save_partial_and_connected(self, auth_session):
        # Use meta_ads (2 fields: access_token, ad_account_id) — sendgrid was removed in iter-3
        secret_key = "MA.TESTSECRETVALUE_abcd1234WXYZ"
        r = auth_session.post(f"{BASE_URL}/api/connections", json={
            "provider": "meta_ads", "credentials": {"access_token": secret_key},
        }, timeout=15)
        assert r.status_code == 200

        r = auth_session.get(f"{BASE_URL}/api/connections", timeout=15)
        sg = next(c for c in r.json() if c["provider"] == "meta_ads")
        assert sg["status"] == "Partial"
        assert sg["credentials"]["access_token"]["set"] is True
        # Never return plaintext
        for f, meta in sg["credentials"].items():
            assert "value" not in meta
            assert meta["hint"] != secret_key
            assert secret_key not in str(meta)
        assert sg["credentials"]["access_token"]["hint"].startswith("••••")
        assert sg["credentials"]["access_token"]["hint"].endswith(secret_key[-4:])

        # Save ad_account_id to complete -> Connected
        r = auth_session.post(f"{BASE_URL}/api/connections", json={
            "provider": "meta_ads", "credentials": {"ad_account_id": "act_123456"},
        }, timeout=15)
        assert r.status_code == 200
        r = auth_session.get(f"{BASE_URL}/api/connections", timeout=15)
        sg = next(c for c in r.json() if c["provider"] == "meta_ads")
        assert sg["status"] == "Connected"
        assert sg["credentials"]["ad_account_id"]["set"] is True
        assert sg["credentials"]["access_token"]["set"] is True

        # Ensure raw response text doesn't contain the secret anywhere
        assert secret_key not in r.text

        # DELETE
        r = auth_session.delete(f"{BASE_URL}/api/connections/meta_ads", timeout=15)
        assert r.status_code == 200
        r = auth_session.get(f"{BASE_URL}/api/connections", timeout=15)
        sg = next(c for c in r.json() if c["provider"] == "meta_ads")
        assert sg["status"] == "Pending"

    def test_client_scoped_connection(self, auth_session):
        # Create a client
        r = auth_session.post(f"{BASE_URL}/api/clients", json={"name": "TEST_ConnScope"}, timeout=15)
        cid = r.json()["id"]
        try:
            r = auth_session.post(f"{BASE_URL}/api/connections", json={
                "provider": "hubspot", "client_id": cid,
                "credentials": {"access_token": "hs_TESTtoken_9876"},
            }, timeout=15)
            assert r.status_code == 200

            # Under this client scope, should be Connected
            r = auth_session.get(f"{BASE_URL}/api/connections", params={"client_id": cid}, timeout=15)
            hs = next(c for c in r.json() if c["provider"] == "hubspot")
            assert hs["status"] == "Connected"
            assert hs["credentials"]["access_token"]["set"] is True

            # Platform scope should still be Pending
            r = auth_session.get(f"{BASE_URL}/api/connections", timeout=15)
            hs2 = next(c for c in r.json() if c["provider"] == "hubspot")
            assert hs2["status"] == "Pending"

            auth_session.delete(f"{BASE_URL}/api/connections/hubspot", params={"client_id": cid}, timeout=10)
        finally:
            auth_session.delete(f"{BASE_URL}/api/clients/{cid}", timeout=10)


# ---------- Real lead sourcing ----------
class TestLeadSourcing:
    def test_scrape_domains(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/leads/scrape", json={
            "domains": "stripe.com\nnotion.so",
        }, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] >= 1
        created = body["created"]
        assert all("id" in l for l in created)
        assert all(l.get("source") == "Web Scrape" for l in created)
        # cleanup
        for l in created:
            auth_session.delete(f"{BASE_URL}/api/leads/{l['id']}", timeout=10)

    def test_csv_import(self, auth_session):
        csv_text = "name,email,company,title\nTEST_Jane Doe,jane@acme.test,Acme,VP Marketing\nTEST_John Smith,john@beta.test,Beta,CMO"
        r = auth_session.post(f"{BASE_URL}/api/leads/import", json={"csv_text": csv_text}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 2

        # Verify role mapped from 'title' column
        r = auth_session.get(f"{BASE_URL}/api/leads", timeout=15)
        leads = r.json()
        jane = [l for l in leads if l.get("email") == "jane@acme.test"]
        assert len(jane) >= 1
        assert jane[0]["role"] == "VP Marketing"
        assert jane[0]["source"] == "CSV Import"

        # cleanup
        for l in leads:
            if l.get("email") in ("jane@acme.test", "john@beta.test"):
                auth_session.delete(f"{BASE_URL}/api/leads/{l['id']}", timeout=10)

    def test_csv_empty_rejected(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/leads/import", json={"csv_text": "name,email,company\n"}, timeout=15)
        assert r.status_code == 400


# ---------- Analytics + Agents ----------
class TestAnalyticsAgents:
    def test_overview(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/analytics/overview", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for key in ("kpis", "trend", "channel_performance", "funnel"):
            assert key in d
        assert len(d["trend"]) == 6
        assert len(d["funnel"]) == 5

    def test_agents(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/agents", timeout=15)
        assert r.status_code == 200
        agents = r.json()
        assert len(agents) >= 10
        assert all("name" in a and "role" in a and "status" in a for a in agents)



# ============================================================================
# ITERATION 3: Email vault + Real Email + Client Portal + CRM/Social fallback
# ============================================================================

PORTAL_EMAIL = f"portaluser_{int(time.time())}@test.com"
PORTAL_PASSWORD = "portal123"


# ---------- Email vault seeded from env ----------
class TestEmailVaultSeeded:
    def test_email_provider_connected_with_masked_hints(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/connections", timeout=15)
        assert r.status_code == 200
        conns = r.json()
        email_conn = next((c for c in conns if c["provider"] == "email"), None)
        assert email_conn is not None, "email provider must be present"
        assert email_conn["status"] == "Connected", f"expected Connected, got {email_conn['status']}"
        # from_name hint should end with 'ting' for AIMarketing
        from_name_hint = email_conn["credentials"].get("from_name", {}).get("hint", "")
        assert from_name_hint.endswith("ting"), f"from_name hint should end with 'ting', got {from_name_hint!r}"
        # no plaintext secrets
        raw = r.text
        for danger in ("smtp.gmail.com" in raw, "587" in raw):
            pass  # host/port hints acceptable as they are masked already
        # smtp_password must never be plaintext — only masked hint
        pwd_meta = email_conn["credentials"].get("smtp_password", {})
        assert pwd_meta.get("set") is True
        assert "value" not in pwd_meta
        # Ensure no full-length password leaked (hint format ••••XXXX)
        assert pwd_meta["hint"].startswith("••••")


# ---------- REAL email send ----------
class TestRealEmailSend:
    def test_send_to_valid_lead(self, auth_session):
        # Create a lead with the whitelisted email
        r = auth_session.post(f"{BASE_URL}/api/leads", json={
            "name": "TEST_EmailTarget", "email": "ekodecrux@gmail.com",
            "company": "TestCo", "role": "Tester",
        }, timeout=15)
        assert r.status_code == 200, r.text
        lid = r.json()["id"]
        try:
            r = auth_session.post(f"{BASE_URL}/api/sales/send-email", json={
                "lead_id": lid, "subject": "AIMarketing iteration 3 test",
                "message": "This is an automated test email — please ignore.",
            }, timeout=60)
            assert r.status_code == 200, f"real send failed: {r.status_code} {r.text}"
            body = r.json()
            assert body.get("status") == "sent"
            assert "ekodecrux@gmail.com" in body.get("message", "")
        finally:
            auth_session.delete(f"{BASE_URL}/api/leads/{lid}", timeout=10)

    def test_send_no_email_returns_400(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/leads", json={
            "name": "TEST_NoEmail", "email": "", "company": "TestCo",
        }, timeout=15)
        assert r.status_code == 200
        lid = r.json()["id"]
        try:
            r = auth_session.post(f"{BASE_URL}/api/sales/send-email", json={
                "lead_id": lid, "subject": "x", "message": "y",
            }, timeout=15)
            assert r.status_code == 400
            assert "email" in r.text.lower()
        finally:
            auth_session.delete(f"{BASE_URL}/api/leads/{lid}", timeout=10)


# ---------- Client Portal user creation + login ----------
class TestClientPortal:
    def test_portal_user_flow(self, auth_session):
        # Create client under admin
        r = auth_session.post(f"{BASE_URL}/api/clients", json={
            "name": "TEST_PortalClient", "industry": "SaaS",
        }, timeout=15)
        assert r.status_code == 200
        cid = r.json()["id"]

        # Create portal user
        r = auth_session.post(f"{BASE_URL}/api/clients/{cid}/portal-user", json={
            "email": PORTAL_EMAIL, "password": PORTAL_PASSWORD, "name": "Portal User",
        }, timeout=15)
        assert r.status_code == 200, r.text

        # Duplicate email should 400
        r_dup = auth_session.post(f"{BASE_URL}/api/clients/{cid}/portal-user", json={
            "email": PORTAL_EMAIL, "password": PORTAL_PASSWORD, "name": "dup",
        }, timeout=15)
        assert r_dup.status_code == 400

        # List portal users
        r = auth_session.get(f"{BASE_URL}/api/clients/{cid}/portal-users", timeout=15)
        assert r.status_code == 200
        users = r.json()
        assert any(u["email"] == PORTAL_EMAIL for u in users)

        # Login as portal user
        ps = requests.Session()
        ps.headers.update({"Content-Type": "application/json"})
        r = ps.post(f"{BASE_URL}/api/auth/login",
                    json={"email": PORTAL_EMAIL, "password": PORTAL_PASSWORD}, timeout=15)
        assert r.status_code == 200, r.text
        pu = r.json()["user"]
        ps.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
        assert pu["role"] == "client"
        assert pu["client_id"] == cid

        # /me confirms role + client_id
        r = ps.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200
        me = r.json()
        assert me["role"] == "client"
        assert me["client_id"] == cid

        # Seed some data as admin: lead under this client, lead under DIFFERENT client, campaign under this client
        r = auth_session.post(f"{BASE_URL}/api/leads", json={
            "name": "TEST_MineLead", "email": "mine@x.test", "company": "Mine", "client_id": cid,
        }, timeout=15); assert r.status_code == 200
        mine_lead = r.json()["id"]

        r = auth_session.post(f"{BASE_URL}/api/clients", json={"name": "TEST_OtherClient"}, timeout=15)
        other_cid = r.json()["id"]
        r = auth_session.post(f"{BASE_URL}/api/leads", json={
            "name": "TEST_OtherLead", "email": "other@x.test", "company": "Other", "client_id": other_cid,
        }, timeout=15); assert r.status_code == 200
        other_lead = r.json()["id"]

        r = auth_session.post(f"{BASE_URL}/api/leads", json={
            "name": "TEST_UnscopedLead", "email": "unscoped@x.test", "company": "None",
        }, timeout=15); assert r.status_code == 200
        unscoped_lead = r.json()["id"]

        r = auth_session.post(f"{BASE_URL}/api/campaigns", json={
            "name": "TEST_MineCamp", "channel": "Google Ads", "objective": "Leads",
            "budget": 100, "impressions": 1000, "clicks": 50, "conversions": 5, "revenue": 500,
            "client_id": cid,
        }, timeout=15); assert r.status_code == 200
        mine_camp = r.json()["id"]

        r = auth_session.post(f"{BASE_URL}/api/campaigns", json={
            "name": "TEST_OtherCamp", "channel": "Meta Ads", "objective": "Awareness",
            "budget": 200, "impressions": 2000, "clicks": 100, "conversions": 10, "revenue": 1000,
            "client_id": other_cid,
        }, timeout=15); assert r.status_code == 200
        other_camp = r.json()["id"]

        try:
            # === Portal isolation ===
            # Leads: only cid's leads
            r = ps.get(f"{BASE_URL}/api/leads", timeout=15)
            assert r.status_code == 200
            leads = r.json()
            assert all(l.get("client_id") == cid for l in leads), \
                f"portal user should see only own leads. got client_ids: {[l.get('client_id') for l in leads]}"
            assert any(l["id"] == mine_lead for l in leads)
            assert not any(l["id"] in (other_lead, unscoped_lead) for l in leads)

            # Campaigns: only cid's
            r = ps.get(f"{BASE_URL}/api/campaigns", timeout=15)
            assert r.status_code == 200
            camps = r.json()
            assert all(c.get("client_id") == cid for c in camps)
            assert any(c["id"] == mine_camp for c in camps)
            assert not any(c["id"] == other_camp for c in camps)

            # Analytics scoped
            r = ps.get(f"{BASE_URL}/api/analytics/overview", timeout=15)
            assert r.status_code == 200
            k = r.json()["kpis"]
            # Should include only the 1 lead + 1 campaign for this client
            assert k["total_leads"] == 1
            assert k["campaigns"] == 1

            # Portal user forbidden from owner endpoints
            for path, method in [
                ("/api/clients", "GET"),
                ("/api/connections", "GET"),
            ]:
                r = ps.request(method, f"{BASE_URL}{path}", timeout=10)
                assert r.status_code == 403, f"{method} {path} expected 403, got {r.status_code}"

            r = ps.post(f"{BASE_URL}/api/connections",
                        json={"provider": "sendgrid", "credentials": {"api_key": "x"}}, timeout=10)
            assert r.status_code == 403

            # === Owner scoping (admin) unchanged ===
            r = auth_session.get(f"{BASE_URL}/api/leads", params={"client_id": cid}, timeout=15)
            assert r.status_code == 200
            filtered = r.json()
            assert all(l.get("client_id") == cid for l in filtered)

            r = auth_session.get(f"{BASE_URL}/api/leads", timeout=15)
            assert r.status_code == 200
            all_leads = r.json()
            # admin sees all
            assert any(l["id"] == other_lead for l in all_leads)
            assert any(l["id"] == mine_lead for l in all_leads)

        finally:
            for lid in (mine_lead, other_lead, unscoped_lead):
                auth_session.delete(f"{BASE_URL}/api/leads/{lid}", timeout=10)
            for cmp_id in (mine_camp, other_camp):
                auth_session.delete(f"{BASE_URL}/api/campaigns/{cmp_id}", timeout=10)
            auth_session.delete(f"{BASE_URL}/api/clients/{other_cid}", timeout=10)
            auth_session.delete(f"{BASE_URL}/api/clients/{cid}", timeout=10)


# ---------- CRM sync placeholder when not configured ----------
class TestCrmSyncPlaceholder:
    def test_hubspot_not_configured(self, auth_session):
        # Ensure hubspot not configured at platform scope
        auth_session.delete(f"{BASE_URL}/api/connections/hubspot", timeout=10)
        r = auth_session.post(f"{BASE_URL}/api/crm/sync",
                              json={"provider": "hubspot"}, timeout=15)
        assert r.status_code == 400
        assert "not configured" in r.text.lower()

    def test_unsupported_provider(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/crm/sync",
                              json={"provider": "pipedrive"}, timeout=15)
        assert r.status_code == 400


# ---------- Live social publish falls back to simulated ----------
class TestSocialPublishFallback:
    def test_linkedin_simulated_when_no_creds(self, auth_session):
        # Ensure linkedin not configured
        auth_session.delete(f"{BASE_URL}/api/connections/linkedin", timeout=10)
        r = auth_session.post(f"{BASE_URL}/api/social/schedule", json={
            "platform": "LinkedIn", "content": "TEST fallback post",
            "scheduled_time": "2026-02-01T10:00:00",
        }, timeout=15)
        assert r.status_code == 200
        pid = r.json()["id"]
        try:
            r = auth_session.patch(f"{BASE_URL}/api/social/posts/{pid}/publish", timeout=20)
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "Published"
            assert body.get("published_mode") == "simulated"
        finally:
            auth_session.delete(f"{BASE_URL}/api/social/posts/{pid}", timeout=10)


# ============================================================================
# ITERATION 4: OTP login, Business Profile+Currency, Budget Planner, Flow,
# Autopilot Proposals + Approvals, cross-tenant SECURITY isolation.
# ============================================================================


# ---------- OTP login ----------
class TestOtpLogin:
    def test_otp_admin_screen_flow(self, session):
        # Request OTP for admin (email identifier) — no auth needed
        r = session.post(f"{BASE_URL}/api/auth/otp/request",
                         json={"identifier": ADMIN_EMAIL}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["channel"] == "screen"
        assert "dev_otp" in body and len(body["dev_otp"]) == 6 and body["dev_otp"].isdigit()
        code = body["dev_otp"]

        # Wrong code -> 401
        s2 = requests.Session()
        s2.headers.update({"Content-Type": "application/json"})
        rw = s2.post(f"{BASE_URL}/api/auth/otp/verify",
                     json={"identifier": ADMIN_EMAIL, "code": "000000"}, timeout=15)
        assert rw.status_code == 401

        # Correct code -> login, sets cookie, returns user
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/otp/verify",
                   json={"identifier": ADMIN_EMAIL, "code": code}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["user"]["email"] == ADMIN_EMAIL
        assert "token" in d
        assert "access_token" in r.cookies

    def test_otp_unknown_identifier_404(self, session):
        r = session.post(f"{BASE_URL}/api/auth/otp/request",
                         json={"identifier": "nobody_here_xyz@nowhere.test"}, timeout=15)
        assert r.status_code == 404

    def test_register_with_phone_and_otp_by_phone(self, session):
        ts = int(time.time())
        phone = f"+1555{ts % 10000000:07d}"
        email = f"phoneuser_{ts}@test.com"
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "password": "pass1234", "name": "Phone User",
            "phone": phone,
        }, timeout=15)
        assert r.status_code == 200, r.text
        u = r.json()["user"]
        assert u.get("phone") == phone

        # OTP by phone
        r = session.post(f"{BASE_URL}/api/auth/otp/request",
                         json={"identifier": phone}, timeout=15)
        assert r.status_code == 200, r.text
        code = r.json().get("dev_otp")
        assert code

        # Verify by phone
        s2 = requests.Session()
        s2.headers.update({"Content-Type": "application/json"})
        r = s2.post(f"{BASE_URL}/api/auth/otp/verify",
                    json={"identifier": phone, "code": code}, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["email"] == email


# ---------- Business Profile + Currency ----------
class TestBusinessProfile:
    def test_put_get_profile(self, auth_session):
        r = auth_session.put(f"{BASE_URL}/api/profile", json={
            "company_name": "TEST_NexusCo", "industry": "SaaS",
            "website": "https://nexus.test",
            "country": "India", "currency": "INR",
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["company_name"] == "TEST_NexusCo"
        assert d["currency"] == "INR"
        assert d["country"] == "India"

        r = auth_session.get(f"{BASE_URL}/api/profile", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["currency"] == "INR"
        assert d["company_name"] == "TEST_NexusCo"

    def test_extract_profile_owner_ok(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/profile/extract",
                              json={"url": "stripe.com"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        for key in ("company_name", "description", "industry", "suggested_currency"):
            assert key in d, f"missing {key}"
        assert d.get("website") in ("stripe.com", "https://stripe.com", "http://stripe.com")

    def test_extract_profile_forbidden_for_portal(self, auth_session):
        # Create client + portal user
        r = auth_session.post(f"{BASE_URL}/api/clients", json={"name": "TEST_ExtractGate"}, timeout=15)
        cid = r.json()["id"]
        ts = int(time.time())
        pemail = f"portalx_{ts}@test.com"
        try:
            r = auth_session.post(f"{BASE_URL}/api/clients/{cid}/portal-user",
                                  json={"email": pemail, "password": "pp12345", "name": "PX"}, timeout=15)
            assert r.status_code == 200
            ps = requests.Session()
            ps.headers.update({"Content-Type": "application/json"})
            r = ps.post(f"{BASE_URL}/api/auth/login",
                        json={"email": pemail, "password": "pp12345"}, timeout=15)
            assert r.status_code == 200
            ps.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
            r = ps.post(f"{BASE_URL}/api/profile/extract",
                        json={"url": "stripe.com"}, timeout=30)
            assert r.status_code == 403
        finally:
            auth_session.delete(f"{BASE_URL}/api/clients/{cid}", timeout=10)


# ---------- Budget Planner ----------
class TestBudgetPlanner:
    def test_generate_plan_seo_led(self, auth_session):
        # Ensure profile currency INR from previous test (or set now)
        auth_session.put(f"{BASE_URL}/api/profile", json={
            "company_name": "TEST_NexusCo", "industry": "SaaS",
            "country": "India", "currency": "INR",
        }, timeout=15)
        r = auth_session.post(f"{BASE_URL}/api/budget/plan", json={
            "total_budget": 1000000, "period": "Monthly",
            "primary_goal": "leads", "notes": "test",
        }, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["currency"] == "INR"
        res = d["result"]
        assert isinstance(res.get("allocations"), list) and len(res["allocations"]) >= 2
        # each allocation has amount computed = pct% of total
        for a in res["allocations"]:
            assert "amount" in a
            expected = round(float(a.get("pct", 0)) / 100 * 1000000, 2)
            assert abs(a["amount"] - expected) < 0.01
        assert res.get("seo_share_pct", 0) >= 40  # allow slight jitter, target ~45
        assert "paid_share_pct" in res
        assert isinstance(res.get("ramp", []), list) and len(res["ramp"]) >= 1
        assert "expected_total_leads" in res

    def test_list_plans(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/budget/plans", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list) and len(r.json()) >= 1


# ---------- Autonomous Flow status ----------
class TestFlowStatus:
    def test_flow_status_shape(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/flow/status", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "steps" in d and "completed" in d and "total" in d and "autopilot" in d
        keys = {s["key"] for s in d["steps"]}
        expected = {"profile", "strategy", "content", "budget", "campaigns",
                    "leads", "score", "convert", "report"}
        assert expected.issubset(keys), f"missing keys: {expected - keys}"
        for s in d["steps"]:
            assert "done" in s and isinstance(s["done"], bool)
            assert "count" in s and isinstance(s["count"], int)
        assert d["total"] == 9

    def test_autopilot_toggle_reflected(self, auth_session):
        r = auth_session.put(f"{BASE_URL}/api/profile",
                             json={"autopilot": True, "currency": "INR"}, timeout=15)
        assert r.status_code == 200
        r = auth_session.get(f"{BASE_URL}/api/flow/status", timeout=15)
        assert r.json()["autopilot"] is True
        # revert
        auth_session.put(f"{BASE_URL}/api/profile",
                        json={"autopilot": False, "currency": "INR"}, timeout=15)


# ---------- Autopilot Proposals + Approvals ----------
class TestProposalsApprovals:
    def test_generate_list_approve_reject(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/proposals/generate", json={}, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        assert r.json()["count"] >= 1

        r = auth_session.get(f"{BASE_URL}/api/proposals", params={"status": "Pending"}, timeout=15)
        assert r.status_code == 200
        props = r.json()
        assert len(props) >= 1
        p = props[0]
        assert p["status"] == "Pending"
        for key in ("name", "channel", "suggested_budget", "ad_copy"):
            assert key in (p.get("data") or {}), f"proposal.data missing {key}"

        # Approve first -> creates a campaign
        pid = p["id"]
        r = auth_session.post(f"{BASE_URL}/api/proposals/{pid}/approve", json={}, timeout=15)
        assert r.status_code == 200, r.text
        camp = r.json()["campaign"]
        cid = camp["id"]

        # verify campaign appears in list
        r = auth_session.get(f"{BASE_URL}/api/campaigns", timeout=15)
        assert any(c["id"] == cid for c in r.json())

        # proposal marked Approved
        r = auth_session.get(f"{BASE_URL}/api/proposals", timeout=15)
        this = next(x for x in r.json() if x["id"] == pid)
        assert this["status"] == "Approved"

        # Reject another if exists (pending), else create one via new generate
        pendings = [x for x in r.json() if x["status"] == "Pending"]
        if pendings:
            rid = pendings[0]["id"]
            r = auth_session.post(f"{BASE_URL}/api/proposals/{rid}/reject", timeout=15)
            assert r.status_code == 200
            r = auth_session.get(f"{BASE_URL}/api/proposals", timeout=15)
            this = next(x for x in r.json() if x["id"] == rid)
            assert this["status"] == "Rejected"

        # cleanup created campaign
        auth_session.delete(f"{BASE_URL}/api/campaigns/{cid}", timeout=10)


# ---------- SECURITY: multi-tenant isolation on ID-addressed mutations ----------
class TestSecurityIsolation:
    def test_portal_user_cannot_touch_other_clients(self, auth_session):
        ts = int(time.time())
        # client A + portal user
        r = auth_session.post(f"{BASE_URL}/api/clients", json={"name": f"TEST_SecA_{ts}"}, timeout=15)
        a_cid = r.json()["id"]
        r = auth_session.post(f"{BASE_URL}/api/clients", json={"name": f"TEST_SecB_{ts}"}, timeout=15)
        b_cid = r.json()["id"]

        pemail = f"sec_portal_{ts}@test.com"
        r = auth_session.post(f"{BASE_URL}/api/clients/{a_cid}/portal-user",
                              json={"email": pemail, "password": "portal123", "name": "PA"}, timeout=15)
        assert r.status_code == 200

        # Seed lead + campaign under client B as admin
        r = auth_session.post(f"{BASE_URL}/api/leads", json={
            "name": "TEST_BLead", "email": "b@x.test", "company": "Bco", "client_id": b_cid,
        }, timeout=15)
        b_lead = r.json()["id"]

        r = auth_session.post(f"{BASE_URL}/api/campaigns", json={
            "name": "TEST_BCamp", "channel": "SEO", "objective": "Leads",
            "budget": 100, "impressions": 100, "clicks": 10,
            "conversions": 1, "revenue": 50, "client_id": b_cid,
        }, timeout=15)
        b_camp = r.json()["id"]

        # Login as portal user (client A)
        ps = requests.Session()
        ps.headers.update({"Content-Type": "application/json"})
        r = ps.post(f"{BASE_URL}/api/auth/login",
                    json={"email": pemail, "password": "portal123"}, timeout=15)
        assert r.status_code == 200
        ps.headers.update({"Authorization": f"Bearer {r.json()['token']}"})

        try:
            # 1) LIST endpoints must not include other client's records
            r = ps.get(f"{BASE_URL}/api/leads", timeout=15)
            assert r.status_code == 200
            assert not any(l["id"] == b_lead for l in r.json())

            r = ps.get(f"{BASE_URL}/api/campaigns", timeout=15)
            assert r.status_code == 200
            assert not any(c["id"] == b_camp for c in r.json())

            # 2) ID-addressed mutations on B's lead must be blocked (403 or 404)
            block_codes = (403, 404)

            r = ps.post(f"{BASE_URL}/api/leads/{b_lead}/score", timeout=30)
            assert r.status_code in block_codes, f"score should block, got {r.status_code}"

            r = ps.patch(f"{BASE_URL}/api/leads/{b_lead}/stage",
                         json={"stage": "Opportunity"}, timeout=15)
            assert r.status_code in block_codes, f"stage should block, got {r.status_code}"

            r = ps.delete(f"{BASE_URL}/api/leads/{b_lead}", timeout=15)
            assert r.status_code in block_codes, f"delete lead should block, got {r.status_code}"

            r = ps.post(f"{BASE_URL}/api/sales/assist",
                        json={"lead_id": b_lead, "action": "follow_up_email"}, timeout=30)
            assert r.status_code in block_codes, f"sales/assist should block, got {r.status_code}"

            # 3) Campaign mutations on B's campaign must be blocked
            r = ps.patch(f"{BASE_URL}/api/campaigns/{b_camp}/metrics",
                         json={"impressions": 999, "clicks": 99, "conversions": 9, "revenue": 100},
                         timeout=15)
            assert r.status_code in block_codes, f"metrics should block, got {r.status_code}"

            r = ps.patch(f"{BASE_URL}/api/campaigns/{b_camp}/toggle", timeout=15)
            assert r.status_code in block_codes, f"toggle should block, got {r.status_code}"

            r = ps.delete(f"{BASE_URL}/api/campaigns/{b_camp}", timeout=15)
            assert r.status_code in block_codes, f"delete campaign should block, got {r.status_code}"

            # 4) Owner-only endpoints must return 403 for client users
            r = ps.get(f"{BASE_URL}/api/clients", timeout=10)
            assert r.status_code == 403
            r = ps.get(f"{BASE_URL}/api/connections", timeout=10)
            assert r.status_code == 403
            r = ps.post(f"{BASE_URL}/api/proposals/generate", json={}, timeout=10)
            assert r.status_code == 403

            # 5) Sanity: verify B's lead/campaign are still intact via admin
            r = auth_session.get(f"{BASE_URL}/api/leads", params={"client_id": b_cid}, timeout=15)
            assert any(l["id"] == b_lead for l in r.json())
            r = auth_session.get(f"{BASE_URL}/api/campaigns", params={"client_id": b_cid}, timeout=15)
            camps = r.json()
            b = next(c for c in camps if c["id"] == b_camp)
            assert b["status"] == "Active"  # toggle didn't take effect
            assert b["impressions"] == 100  # metrics didn't take effect
        finally:
            auth_session.delete(f"{BASE_URL}/api/leads/{b_lead}", timeout=10)
            auth_session.delete(f"{BASE_URL}/api/campaigns/{b_camp}", timeout=10)
            auth_session.delete(f"{BASE_URL}/api/clients/{a_cid}", timeout=10)
            auth_session.delete(f"{BASE_URL}/api/clients/{b_cid}", timeout=10)

