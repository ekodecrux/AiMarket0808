import asyncio
import os
import pathlib
import sys
import unittest

import jwt
from bson import ObjectId
from fastapi import HTTPException

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from auth import JWT_ALGORITHM, JWT_ISSUER, create_access_token, generate_temporary_password, validate_new_password


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

    def test_webhook_rejects_bad_signature_before_payment_mutation(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "server.py").read_text()
        route = source[source.index("async def payment_webhook"):source.index("async def payment_webhook") + 2300]
        self.assertIn("if not valid or not event_id:", route)
        self.assertIn("raise HTTPException(400", route)
        self.assertLess(route.index("raise HTTPException(400"), route.index("db.payments.update_one"))
        self.assertIn("payment_events.create_index", source)


if __name__ == "__main__":
    unittest.main()
