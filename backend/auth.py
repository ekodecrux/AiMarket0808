import hashlib
import os
import re
import secrets
import string
import urllib.parse
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from bson import ObjectId
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pymongo import ReturnDocument

from models import (
    RegisterInput, LoginInput, OtpRequestInput, OtpVerifyInput,
    PasswordChangeInput, PasswordResetConfirmInput, PasswordResetRequestInput, now_utc,
)

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "aimarket-nexus"
ACCESS_TOKEN_DAYS = 7
PASSWORD_MIN_LENGTH = 12
RESET_TOKEN_MINUTES = 30


async def _system_conn_creds(db, provider: str) -> dict:
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
    return await _system_conn_creds(db, "twilio_verify")


async def _system_email_creds(db) -> dict:
    """Prefer protected deployment env; retain encrypted legacy connection as a migration fallback."""
    configured = {
        "smtp_host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": os.environ.get("SMTP_PORT", "587"),
        "smtp_user": os.environ.get("SMTP_USER", ""),
        "smtp_password": os.environ.get("SMTP_PASSWORD", ""),
        "from_email": os.environ.get("EMAIL_FROM", os.environ.get("SMTP_USER", "")),
        "from_name": os.environ.get("EMAIL_FROM_NAME", "AiMarket NEXUS"),
    }
    if all(configured.get(k) for k in ("smtp_host", "smtp_user", "smtp_password")):
        return configured
    return await _system_conn_creds(db, "email")


def get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret or len(secret) < 32:
        raise RuntimeError("JWT_SECRET must be configured with at least 32 characters")
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def validate_new_password(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH or len(password) > 128:
        raise HTTPException(422, f"Password must be {PASSWORD_MIN_LENGTH}–128 characters")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(422, "Password must include at least one letter and one number")


def generate_temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%*_-"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(16))
        if re.search(r"[a-z]", password) and re.search(r"[A-Z]", password) and re.search(r"\d", password):
            return password


def _tenant_id(user: dict) -> str:
    return user.get("tenant_id") or user.get("owner_id") or str(user["_id"])


def create_access_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": str(user["_id"]), "email": user["email"], "tid": _tenant_id(user),
        "role": user.get("role", "user"), "ver": int(user.get("token_version", 0)),
        "iss": JWT_ISSUER, "iat": now, "exp": now + timedelta(days=ACCESS_TOKEN_DAYS), "type": "access",
    }, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _set_cookie(response: Response, token: str):
    response.set_cookie(key="access_token", value=token, httponly=True, secure=True,
                        samesite="none", max_age=ACCESS_TOKEN_DAYS * 86400, path="/")


def _public_user(user: dict) -> dict:
    return {"id": str(user["_id"]), "email": user["email"], "name": user.get("name", ""),
            "role": user.get("role", "user"), "tenant_id": _tenant_id(user),
            "client_id": user.get("client_id"), "phone": user.get("phone", ""),
            "must_change_password": bool(user.get("password_change_required", False))}


async def _send_auth_email(db, to_email: str, subject: str, plain: str, html: str = "") -> None:
    import integrations_live as live
    creds = await _system_email_creds(db)
    if not creds:
        raise HTTPException(503, "Email delivery is not configured")
    try:
        sent, _ = await live.send_email(creds, to_email, subject, plain, html)
    except Exception:
        sent = False
    if not sent:
        raise HTTPException(502, "Email delivery is temporarily unavailable")


async def _consume_rate_limit(db, kind: str, key: str, limit: int, minutes: int) -> bool:
    now = now_utc()
    key_hash = hashlib.sha256(key.lower().encode("utf-8")).hexdigest()
    record = await db.auth_rate_limits.find_one_and_update(
        {"kind": kind, "key_hash": key_hash, "$or": [{"expires_at": {"$gt": now}}, {"expires_at": {"$exists": False}}]},
        {"$inc": {"count": 1}, "$setOnInsert": {"created_at": now, "expires_at": now + timedelta(minutes=minutes)}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    return int(record.get("count", 0)) <= limit


async def _issue_reset_token(db, user: dict) -> str:
    raw = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "user_id": str(user["_id"]), "tenant_id": _tenant_id(user),
        "token_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "created_at": now_utc(), "expires_at": now_utc() + timedelta(minutes=RESET_TOKEN_MINUTES), "used_at": None,
    })
    return raw


async def _apply_password(db, user: dict, password: str, require_change: bool) -> None:
    validate_new_password(password)
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(password),
        "password_change_required": require_change, "password_changed_at": now_utc()}, "$inc": {"token_version": 1}})


def create_auth_router(db):
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    async def get_current_user(request: Request) -> dict:
        token = request.cookies.get("access_token")
        if not token:
            header = request.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else None
        if not token:
            raise HTTPException(401, "Not authenticated")
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)
            if payload.get("type") != "access":
                raise HTTPException(401, "Invalid token")
            user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
            if not user or payload.get("ver") != int(user.get("token_version", 0)) or payload.get("tid") != _tenant_id(user):
                raise HTTPException(401, "Session expired")
            return user
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, TypeError):
            raise HTTPException(401, "Invalid or expired session")

    @router.post("/register")
    async def register(data: RegisterInput, response: Response):
        email = str(data.email).lower().strip()
        if await db.users.find_one({"email": email}):
            raise HTTPException(400, "Email already registered")
        password = generate_temporary_password() if data.use_generated_password else (data.password or "")
        if not data.use_generated_password:
            validate_new_password(password)
        user_id = ObjectId()
        user = {"_id": user_id, "email": email, "password_hash": hash_password(password), "name": data.name.strip(),
                "phone": data.phone or "", "role": "user", "tenant_id": str(user_id), "token_version": 0,
                "password_change_required": bool(data.use_generated_password), "created_at": now_utc(), "password_changed_at": now_utc()}
        await db.users.insert_one(user)
        await db.tenants.update_one({"_id": str(user_id)}, {"$setOnInsert": {"_id": str(user_id), "owner_user_id": str(user_id),
            "name": data.name.strip() or email, "created_at": now_utc()}}, upsert=True)
        if data.use_generated_password:
            try:
                await _send_auth_email(db, email, "Your AiMarket NEXUS temporary password",
                    f"Your temporary password is: {password}\n\nSign in and change it immediately in Workspace > Account. Do not share this password.")
            except HTTPException:
                await db.users.delete_one({"_id": user_id})
                await db.tenants.delete_one({"_id": str(user_id)})
                raise
        token = create_access_token(user)
        _set_cookie(response, token)
        return {"user": _public_user(user), "token": token, "temporary_password_emailed": bool(data.use_generated_password)}

    @router.post("/login")
    async def login(data: LoginInput, response: Response):
        email = str(data.email).lower().strip()
        user = await db.users.find_one({"email": email})
        now = now_utc()
        if user and user.get("login_locked_until") and user["login_locked_until"] > now:
            raise HTTPException(401, "Invalid email or password")
        if not user or not verify_password(data.password, user.get("password_hash", "")):
            if user:
                failures = int(user.get("failed_login_count", 0)) + 1
                changes = {"failed_login_count": failures}
                if failures >= 5:
                    changes["login_locked_until"] = now + timedelta(minutes=15)
                await db.users.update_one({"_id": user["_id"]}, {"$set": changes})
            raise HTTPException(401, "Invalid email or password")
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"failed_login_count": 0, "login_locked_until": None, "last_signed_in_at": now}})
        user.update({"failed_login_count": 0, "login_locked_until": None})
        token = create_access_token(user)
        _set_cookie(response, token)
        return {"user": _public_user(user), "token": token}

    @router.post("/password/reset/request")
    async def request_password_reset(data: PasswordResetRequestInput, request: Request):
        email = str(data.email).lower().strip()
        rate_key = f"{email}:{request.client.host if request.client else 'unknown'}"
        allowed = await _consume_rate_limit(db, "password_reset", rate_key, 3, 60)
        generic = {"message": "If an account exists, password instructions have been sent."}
        if not allowed:
            return generic
        user = await db.users.find_one({"email": email})
        if not user:
            return generic
        if data.delivery == "temporary":
            temporary = generate_temporary_password()
            await _apply_password(db, user, temporary, require_change=True)
            try:
                await _send_auth_email(db, email, "Your AiMarket NEXUS temporary password",
                    f"Your temporary password is: {temporary}\n\nSign in and change it immediately in Workspace > Account. Do not share this password.")
            except HTTPException:
                await db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": user.get("password_hash", ""),
                    "password_change_required": bool(user.get("password_change_required", False)), "password_changed_at": user.get("password_changed_at")}, "$inc": {"token_version": 1}})
                raise
        else:
            token = await _issue_reset_token(db, user)
            base = os.environ.get("AUTH_PUBLIC_BASE_URL", "https://aimarket.expertaitutor.com").rstrip("/")
            link = f"{base}/reset-password?token={urllib.parse.quote(token)}"
            await _send_auth_email(db, email, "Reset your AiMarket NEXUS password",
                f"Use this secure link within {RESET_TOKEN_MINUTES} minutes to set a new password:\n{link}\n\nIf you did not request this, you can ignore this email.")
        return generic

    @router.post("/password/reset/confirm")
    async def confirm_password_reset(data: PasswordResetConfirmInput):
        validate_new_password(data.password)
        token_hash = hashlib.sha256(data.token.encode("utf-8")).hexdigest()
        record = await db.password_reset_tokens.find_one_and_update(
            {"token_hash": token_hash, "used_at": None, "expires_at": {"$gt": now_utc()}},
            {"$set": {"used_at": now_utc()}}, return_document=ReturnDocument.AFTER,
        )
        if not record:
            raise HTTPException(400, "This reset link is invalid or expired")
        user = await db.users.find_one({"_id": ObjectId(record["user_id"])})
        if not user:
            raise HTTPException(400, "This reset link is invalid or expired")
        await _apply_password(db, user, data.password, require_change=False)
        return {"message": "Password reset. Sign in with your new password."}

    @router.post("/password/change")
    async def change_password(data: PasswordChangeInput, user: dict = Depends(get_current_user)):
        if not verify_password(data.current_password, user.get("password_hash", "")):
            raise HTTPException(400, "Current password is incorrect")
        if data.current_password == data.new_password:
            raise HTTPException(422, "Choose a new password that differs from the current password")
        await _apply_password(db, user, data.new_password, require_change=False)
        return {"message": "Password changed. Sign in again on this and other devices."}

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
            raise HTTPException(404, "No account found for that email or phone")
        if "@" not in ident_raw:
            creds = await _system_twilio_verify_creds(db)
            if not creds:
                raise HTTPException(503, "SMS OTP is not configured")
            ok, _ = await live.verify_start(creds, user.get("phone", ""))
            if not ok:
                raise HTTPException(502, "Could not send SMS code")
            await db.otps.update_one({"user_id": str(user["_id"])}, {"$set": {"user_id": str(user["_id"]), "channel": "sms", "created_at": now_utc()}}, upsert=True)
            return {"message": "Code sent via SMS", "channel": "sms"}
        code = f"{random.randint(0, 999999):06d}"
        await db.otps.update_one({"user_id": str(user["_id"])}, {"$set": {"user_id": str(user["_id"]), "channel": "email", "code": code,
            "expires_at": now_utc() + timedelta(minutes=5), "created_at": now_utc()}}, upsert=True)
        await _send_auth_email(db, user["email"], "Your AiMarket NEXUS login code", f"Your login code is {code}. It expires in 5 minutes.")
        return {"message": "Code sent to your email", "channel": "email"}

    @router.post("/otp/verify")
    async def otp_verify(data: OtpVerifyInput, response: Response):
        import integrations_live as live
        ident_raw = data.identifier.strip()
        user = await db.users.find_one({"$or": [{"email": ident_raw.lower()}, {"phone": ident_raw}]})
        if not user:
            raise HTTPException(404, "No account found")
        record = await db.otps.find_one({"user_id": str(user["_id"])})
        if not record:
            raise HTTPException(401, "No code requested")
        if record.get("channel") == "sms":
            creds = await _system_twilio_verify_creds(db)
            ok, _ = await live.verify_check(creds, user.get("phone", ""), data.code.strip()) if creds else (False, "")
        else:
            ok = record.get("code") == data.code.strip() and record.get("expires_at", now_utc()) >= now_utc()
        if not ok:
            raise HTTPException(401, "Invalid or expired code")
        await db.otps.delete_one({"user_id": str(user["_id"])})
        token = create_access_token(user)
        _set_cookie(response, token)
        return {"user": _public_user(user), "token": token}

    return router, get_current_user


async def seed_admin(db):
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@marketing.ai").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    admin_phone = os.environ.get("ADMIN_PHONE", "")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        if not admin_password:
            raise RuntimeError("ADMIN_PASSWORD must be configured before creating the administrator")
        admin_id = ObjectId()
        await db.users.insert_one({"_id": admin_id, "email": admin_email, "password_hash": hash_password(admin_password), "name": "Admin",
            "phone": admin_phone, "role": "admin", "tenant_id": str(admin_id), "token_version": 0, "password_change_required": False, "created_at": now_utc()})
        await db.tenants.update_one({"_id": str(admin_id)}, {"$setOnInsert": {"_id": str(admin_id), "owner_user_id": str(admin_id), "name": "AiMarket Platform", "created_at": now_utc()}}, upsert=True)
    else:
        changes = {"tenant_id": _tenant_id(existing), "token_version": int(existing.get("token_version", 0)), "password_change_required": bool(existing.get("password_change_required", False))}
        if admin_phone and existing.get("phone") != admin_phone:
            changes["phone"] = admin_phone
        await db.users.update_one({"_id": existing["_id"]}, {"$set": changes})
