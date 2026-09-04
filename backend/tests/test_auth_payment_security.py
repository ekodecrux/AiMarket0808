import asyncio
import os
import pathlib
import sys
import unittest
from unittest.mock import patch

import jwt
from bson import ObjectId
from fastapi import HTTPException

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from auth import (
    JWT_ALGORITHM, JWT_ISSUER, create_access_token, create_auth_router, generate_temporary_password,
    google_auth_audiences, google_auth_ready, normalize_e164,
    validate_new_password, verify_google_identity_token,
)
from models import PhoneOtpRequestInput


class _EmptyUsers:
    async def find_one(self, *_args, **_kwargs):
        return None


class _ProviderReadinessDb:
    users = _EmptyUsers()


class AuthAndPaymentSecurityTests(unittest.TestCase):
    def setUp(self):
        os.environ["JWT_SECRET"] = "test-only-secret-with-more-than-thirty-two-characters"

    def test_generated_password_is_strong_and_valid(self):
        password = generate_temporary_password()
        self.assertGreaterEqual(len(password), 16)
        self.assertRegex(password, r"[a-z]")
        self.assertRegex(password, r"[A-Z]")
        self.assertRegex(password, r"\d")
        validate_new_password(password)

    def test_user_chosen_password_policy_rejects_weak_values(self):
        for value in ("short1A", "abcdefghijklmnop", "1234567890123456"):
            with self.assertRaises(HTTPException):
                validate_new_password(value)

    def test_access_token_carries_tenant_and_session_version(self):
        user_id = ObjectId()
        token = create_access_token({"_id": user_id, "email": "tenant@example.invalid", "tenant_id": "tenant-a", "role": "user", "token_version": 3})
        claims = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)
        self.assertEqual(claims["sub"], str(user_id))
        self.assertEqual(claims["tid"], "tenant-a")
        self.assertEqual(claims["ver"], 3)
        self.assertEqual(claims["iss"], JWT_ISSUER)

    def test_phone_only_session_hides_the_internal_unique_email(self):
        user_id = ObjectId()
        token = create_access_token({"_id": user_id, "email": "phone-internal@users.aimarket.local",
            "phone_auth_only": True, "tenant_id": "tenant-phone", "role": "user", "token_version": 0})
        claims = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)
        self.assertEqual(claims["email"], "")

    def test_webhook_rejects_bad_signature_before_payment_mutation(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "server.py").read_text()
        route = source[source.index("async def payment_webhook"):source.index("async def payment_webhook") + 2300]
        self.assertIn("if not valid or not event_id:", route)
        self.assertIn("raise HTTPException(400", route)
        self.assertLess(route.index("raise HTTPException(400"), route.index("db.payments.update_one"))
        self.assertIn("payment_events.create_index", source)

    def test_google_is_configuration_pending_without_registered_audience(self):
        with patch.dict(os.environ, {"GOOGLE_AUTH_CLIENT_IDS": ""}):
            self.assertFalse(google_auth_ready())
            self.assertEqual(google_auth_audiences(), [])
            with self.assertRaises(HTTPException) as error:
                asyncio.run(verify_google_identity_token("x" * 100, "n" * 32))
        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("not configured", error.exception.detail)

    def test_phone_login_requires_canonical_e164_format(self):
        self.assertEqual(normalize_e164(" +14155552671 "), "+14155552671")
        for invalid in ("14155552671", "+01234567890", "+1415", "+14155552671x"):
            with self.assertRaises(HTTPException) as error:
                normalize_e164(invalid)
            self.assertEqual(error.exception.status_code, 422)

    def test_google_verifier_design_requires_signature_and_nonce_protection(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "auth.py").read_text()
        verifier = source[source.index("async def verify_google_identity_token"):source.index("async def _system_conn_creds")]
        self.assertIn("jwt.PyJWKClient", verifier)
        self.assertIn("audience=audiences", verifier)
        self.assertIn("issuer=list(GOOGLE_ISSUERS)", verifier)
        self.assertIn("secrets.compare_digest", verifier)
        self.assertIn('"email_verified"', verifier)
        self.assertIn("auth_nonces", source)
        self.assertIn('"SMS consent is required', source)
        server_source = (pathlib.Path(__file__).resolve().parents[1] / "server.py").read_text()
        self.assertIn('create_index("google_subject", unique=True, sparse=True)', server_source)
        self.assertIn('create_index("phone", unique=True, partialFilterExpression={"phone": {"$gt": ""}})', server_source)
        self.assertIn("phone_otp_challenges.create_index", server_source)

    def test_provider_readiness_is_safe_when_google_and_twilio_are_unconfigured(self):
        router, _ = create_auth_router(_ProviderReadinessDb())
        endpoint = next(route.endpoint for route in router.routes if route.path.endswith("/providers"))
        with patch.dict(os.environ, {"GOOGLE_AUTH_CLIENT_IDS": "", "GOOGLE_AUTH_WEB_CLIENT_ID": "",
                                     "TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "TWILIO_VERIFY_SERVICE_SID": ""}):
            readiness = asyncio.run(endpoint())
        self.assertFalse(readiness["google"]["available"])
        self.assertEqual(readiness["google"]["web_client_id"], "")
        self.assertFalse(readiness["phone_otp"]["available"])
        self.assertTrue(readiness["phone_otp"]["requires_sms_consent"])

    def test_phone_otp_request_rejects_missing_sms_consent_before_provider_access(self):
        router, _ = create_auth_router(_ProviderReadinessDb())
        endpoint = next(route.endpoint for route in router.routes if route.path.endswith("/otp/phone/request"))
        request_data = PhoneOtpRequestInput(phone="+14155552671", consent=False, intent="login")
        with self.assertRaises(HTTPException) as error:
            asyncio.run(endpoint(request_data))
        self.assertEqual(error.exception.status_code, 422)
        self.assertIn("consent", error.exception.detail.lower())


if __name__ == "__main__":
    unittest.main()
