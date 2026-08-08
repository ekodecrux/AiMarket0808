"""Iteration 5: Autopilot cadence config + Twilio Verify OTP wiring."""
import os
import time
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@marketing.ai"
ADMIN_PASSWORD = "admin123"
ADMIN_PHONE = "+919121664855"
AI_TIMEOUT = 120


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


# ---------------- Autopilot cadence config ----------------
class TestAutopilotConfig:
    def test_get_config_default(self, admin):
        r = admin.get(f"{BASE_URL}/api/autopilot/config", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["is_admin"] is True
        assert isinstance(d["cap"], int) and d["cap"] >= 1
        assert isinstance(d["daily_proposals"], int) and d["daily_proposals"] >= 1
        assert "autopilot" in d and isinstance(d["autopilot"], bool)

    def test_admin_set_cap_6(self, admin):
        r = admin.post(f"{BASE_URL}/api/autopilot/config", json={"cap": 6}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["cap"] == 6
        r = admin.get(f"{BASE_URL}/api/autopilot/config", timeout=15)
        assert r.json()["cap"] == 6

    def test_cap_upper_bound_50(self, admin):
        r = admin.post(f"{BASE_URL}/api/autopilot/config", json={"cap": 999}, timeout=15)
        assert r.status_code == 200
        assert r.json()["cap"] == 50

    def test_cap_lower_bound_1(self, admin):
        r = admin.post(f"{BASE_URL}/api/autopilot/config", json={"cap": 0}, timeout=15)
        assert r.status_code == 200
        assert r.json()["cap"] == 1

    def test_owner_set_daily_proposals(self, admin):
        # reset cap to 6
        admin.post(f"{BASE_URL}/api/autopilot/config", json={"cap": 6}, timeout=15)
        r = admin.post(f"{BASE_URL}/api/autopilot/config", json={"daily_proposals": 4}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["daily_proposals"] == 4
        assert d["cap"] == 6

    def test_daily_proposals_clamped_to_cap(self, admin):
        admin.post(f"{BASE_URL}/api/autopilot/config", json={"cap": 6}, timeout=15)
        r = admin.post(f"{BASE_URL}/api/autopilot/config", json={"daily_proposals": 20}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["daily_proposals"] == 6  # clamped down to current cap
        assert d["cap"] == 6

    def test_generate_matches_daily_proposals(self, admin):
        # Set cap=5 and daily_proposals=2, then generate and expect ~2
        admin.post(f"{BASE_URL}/api/autopilot/config", json={"cap": 5}, timeout=15)
        admin.post(f"{BASE_URL}/api/autopilot/config", json={"daily_proposals": 2}, timeout=15)
        # confirm
        cfg = admin.get(f"{BASE_URL}/api/autopilot/config", timeout=15).json()
        assert cfg["daily_proposals"] == 2 and cfg["cap"] == 5

        r = admin.post(f"{BASE_URL}/api/proposals/generate", json={}, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        n = r.json()["count"]
        # Groq sometimes returns fewer than requested; expect <= configured
        assert 1 <= n <= 2, f"expected count 1-2, got {n}"


# ---------------- OTP: Email (real SMTP) ----------------
class TestOtpEmail:
    def test_email_otp_request_sends(self, admin):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/otp/request",
                   json={"identifier": ADMIN_EMAIL}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["channel"] == "email"
        assert d.get("sent_to") == ADMIN_EMAIL
        # No dev_otp exposed in real email mode
        assert "dev_otp" not in d

    def test_email_otp_verify_wrong_code_401(self, admin):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        # First request an OTP
        r = s.post(f"{BASE_URL}/api/auth/otp/request",
                   json={"identifier": ADMIN_EMAIL}, timeout=30)
        assert r.status_code == 200
        # Then verify with wrong code
        r = s.post(f"{BASE_URL}/api/auth/otp/verify",
                   json={"identifier": ADMIN_EMAIL, "code": "000000"}, timeout=15)
        assert r.status_code == 401, r.text


# ---------------- OTP: Phone (Twilio Verify real SMS) ----------------
class TestOtpPhone:
    def test_phone_otp_request_returns_sms_channel(self, admin):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/otp/request",
                   json={"identifier": ADMIN_PHONE}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["channel"] == "sms"
        sent_to = d.get("sent_to", "")
        # Masked but preserves prefix +91 and last 2 digits
        assert sent_to.startswith("+91"), f"unexpected mask: {sent_to}"
        assert sent_to.endswith(ADMIN_PHONE[-2:])
        assert "•" in sent_to or "*" in sent_to
        # No dev_otp exposed
        assert "dev_otp" not in d

    def test_phone_otp_verify_wrong_code_401(self, admin):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        # Ensure an OTP has been requested first
        r = s.post(f"{BASE_URL}/api/auth/otp/request",
                   json={"identifier": ADMIN_PHONE}, timeout=30)
        assert r.status_code == 200
        r = s.post(f"{BASE_URL}/api/auth/otp/verify",
                   json={"identifier": ADMIN_PHONE, "code": "000000"}, timeout=30)
        assert r.status_code == 401, r.text
        assert "invalid" in r.text.lower() or "expired" in r.text.lower()


# ---------------- OTP: Unknown identifier ----------------
class TestOtpUnknown:
    def test_unknown_email_returns_404(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/otp/request",
                   json={"identifier": f"nobody_{int(time.time())}@nowhere.test"}, timeout=15)
        assert r.status_code == 404

    def test_unknown_phone_returns_404(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/otp/request",
                   json={"identifier": "+10000000000"}, timeout=15)
        assert r.status_code == 404
