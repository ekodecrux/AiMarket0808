import os
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import APIRouter, Request, Response, HTTPException, Depends

from models import RegisterInput, LoginInput, OtpRequestInput, OtpVerifyInput, now_utc

JWT_ALGORITHM = "HS256"


async def _system_conn_creds(db, provider: str) -> dict:
    """Decrypted platform-scope creds for a provider under the admin owner (system sender)."""
    import secrets_store as ss
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").lower()
    admin = await db.users.find_one({"email": admin_email})
    if not admin:
        return {}
    conn = await db.connections.find_one({"user_id": str(admin["_id"]), "client_id": None, "provider": provider})
    if not conn:
        return {}
    fields = ss.PROVIDER_MAP[provider]["fields"]
    creds = {f: ss.decrypt(conn.get("credentials", {}).get(f, "")) for f in fields}
    return creds if all(creds.values()) else {}


async def _system_twilio_verify_creds(db) -> dict:
    """Decrypted platform Twilio Verify creds used as the system OTP sender."""
    import secrets_store as ss
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").lower()
    admin = await db.users.find_one({"email": admin_email})
    if not admin:
        return {}
    conn = await db.connections.find_one({"user_id": str(admin["_id"]), "client_id": None, "provider": "twilio_verify"})
    if not conn:
        return {}
    fields = ss.PROVIDER_MAP["twilio_verify"]["fields"]
    creds = {f: ss.decrypt(conn.get("credentials", {}).get(f, "")) for f in fields}
    return creds if all(creds.values()) else {}


async def _system_email_creds(db) -> dict:
    """Decrypted platform email (SMTP) creds used as the system sender for auth emails."""
    import secrets_store as ss
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").lower()
    admin = await db.users.find_one({"email": admin_email})
    if not admin:
        return {}
    conn = await db.connections.find_one({"user_id": str(admin["_id"]), "client_id": None, "provider": "email"})
    if not conn:
        return {}
    fields = ss.PROVIDER_MAP["email"]["fields"]
    creds = {f: ss.decrypt(conn.get("credentials", {}).get(f, "")) for f in fields}
    if all(creds.get(k) for k in ["smtp_host", "smtp_user", "smtp_password"]):
        return creds
    return {}


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _set_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=604800,
        path="/",
    )


def _public_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "name": user.get("name", ""),
        "role": user.get("role", "user"),
        "client_id": user.get("client_id"),
        "phone": user.get("phone", ""),
    }


def create_auth_router(db):
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    async def get_current_user(request: Request) -> dict:
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    @router.post("/register")
    async def register(data: RegisterInput, response: Response):
        email = data.email.lower().strip()
        if await db.users.find_one({"email": email}):
            raise HTTPException(status_code=400, detail="Email already registered")
        doc = {
            "email": email,
            "password_hash": hash_password(data.password),
            "name": data.name,
            "phone": data.phone or "",
            "role": "user",
            "created_at": now_utc().isoformat(),
        }
        result = await db.users.insert_one(doc)
        doc["_id"] = result.inserted_id
        token = create_access_token(str(result.inserted_id), email)
        _set_cookie(response, token)
        return {"user": _public_user(doc), "token": token}

    @router.post("/login")
    async def login(data: LoginInput, response: Response):
        email = data.email.lower().strip()
        user = await db.users.find_one({"email": email})
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        token = create_access_token(str(user["_id"]), email)
        _set_cookie(response, token)
        return {"user": _public_user(user), "token": token}

    @router.post("/logout")
    async def logout(response: Response):
        response.delete_cookie("access_token", path="/")
        return {"message": "Logged out"}

    @router.get("/me")
    async def me(user: dict = Depends(get_current_user)):
        return _public_user(user)

    @router.post("/otp/request")
    async def otp_request(data: OtpRequestInput):
        import random
        import integrations_live as live
        ident_raw = data.identifier.strip()
        ident = ident_raw.lower()
        user = await db.users.find_one({"$or": [{"email": ident}, {"phone": ident_raw}]})
        if not user:
            raise HTTPException(status_code=404, detail="No account found for that email or phone")

        looks_email = "@" in ident_raw
        phone = user.get("phone", "")

        # PHONE identifier -> real Twilio Verify SMS (no code stored; Twilio manages it)
        if not looks_email:
            if not phone:
                raise HTTPException(status_code=400, detail="No phone number on file for this account")
            tv = await _system_twilio_verify_creds(db)
            if tv:
                try:
                    ok, detail = await live.verify_start(tv, phone)
                    if ok:
                        await db.otps.update_one(
                            {"user_id": str(user["_id"])},
                            {"$set": {"user_id": str(user["_id"]), "channel": "sms", "phone": phone,
                                      "created_at": now_utc().isoformat()}},
                            upsert=True,
                        )
                        masked = (phone[:3] + "•" * max(0, len(phone) - 5) + phone[-2:]) if len(phone) > 5 else phone
                        return {"message": "Code sent via SMS", "channel": "sms", "sent_to": masked}
                    raise HTTPException(status_code=502, detail=f"Could not send SMS code: {str(detail)[:120]}")
                except HTTPException:
                    raise
                except Exception as e:
                    raise HTTPException(status_code=502, detail=f"Could not send SMS code: {str(e)[:120]}")
            raise HTTPException(status_code=503, detail="SMS OTP is not configured. Add Twilio Verify in Settings or sign in with your email.")

        # EMAIL identifier -> real email code via system SMTP sender
        code = f"{random.randint(0, 999999):06d}"
        expires = datetime.now(timezone.utc) + timedelta(minutes=5)
        await db.otps.update_one(
            {"user_id": str(user["_id"])},
            {"$set": {"user_id": str(user["_id"]), "channel": "email", "code": code,
                      "expires_at": expires.isoformat(), "created_at": now_utc().isoformat()}},
            upsert=True,
        )
        body = f"Your AIMarketing login code is {code}. It expires in 5 minutes."
        email_creds = await _system_email_creds(db)
        if email_creds:
            try:
                ok, detail = await live.send_email(email_creds, user["email"], "Your login code", body)
                if ok:
                    return {"message": "Code sent to your email", "channel": "email", "sent_to": user["email"]}
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Could not send code: {str(e)[:120]}")
        raise HTTPException(status_code=503, detail="No delivery channel configured. Add an Email (SMTP) connection in Settings.")

    @router.post("/otp/verify")
    async def otp_verify(data: OtpVerifyInput, response: Response):
        import integrations_live as live
        ident_raw = data.identifier.strip()
        ident = ident_raw.lower()
        user = await db.users.find_one({"$or": [{"email": ident}, {"phone": ident_raw}]})
        if not user:
            raise HTTPException(status_code=404, detail="No account found")
        rec = await db.otps.find_one({"user_id": str(user["_id"])})
        if not rec:
            raise HTTPException(status_code=401, detail="No code requested — request a new one")

        code = data.code.strip()
        if rec.get("channel") == "sms":
            tv = await _system_twilio_verify_creds(db)
            if not tv:
                raise HTTPException(status_code=503, detail="SMS verification unavailable")
            try:
                ok, _ = await live.verify_check(tv, rec.get("phone", user.get("phone", "")), code)
            except Exception:
                ok = False
            if not ok:
                raise HTTPException(status_code=401, detail="Invalid or expired code")
        else:
            if rec.get("code") != code:
                raise HTTPException(status_code=401, detail="Invalid code")
            if datetime.fromisoformat(rec["expires_at"]) < datetime.now(timezone.utc):
                raise HTTPException(status_code=401, detail="Code expired, request a new one")

        await db.otps.delete_one({"user_id": str(user["_id"])})
        token = create_access_token(str(user["_id"]), user["email"])
        _set_cookie(response, token)
        return {"user": _public_user(user), "token": token}

    return router, get_current_user


async def seed_admin(db):
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@marketing.ai").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    admin_phone = os.environ.get("ADMIN_PHONE", "")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Admin",
            "phone": admin_phone,
            "role": "admin",
            "created_at": now_utc().isoformat(),
        })
    else:
        updates = {}
        if not verify_password(admin_password, existing["password_hash"]):
            updates["password_hash"] = hash_password(admin_password)
        if admin_phone and existing.get("phone") != admin_phone:
            updates["phone"] = admin_phone
        if updates:
            await db.users.update_one({"email": admin_email}, {"$set": updates})
