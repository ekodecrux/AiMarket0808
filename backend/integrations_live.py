import asyncio
import logging
import requests
import secrets_store as ss

logger = logging.getLogger(__name__)


async def get_credentials(db, owner_id: str, provider: str, client_id: str = None) -> dict:
    """Resolve credentials for a provider. Prefer client-scoped, fall back to platform."""
    scopes = [client_id, None] if client_id else [None]
    for sc in scopes:
        conn = await db.connections.find_one({"user_id": owner_id, "client_id": sc, "provider": provider})
        if conn:
            stored = conn.get("credentials", {})
            creds = {f: ss.decrypt(stored.get(f, "")) for f in ss.PROVIDER_MAP[provider]["fields"]}
            if all(creds.values()):
                return creds
    return {}


# ---------------- Email (SMTP: Gmail / SendGrid / SES / Resend) ----------------
def _send_smtp(creds, to_email, subject, body, html_body):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from_name = creds.get("from_name") or "AIMarketing"
    from_email = creds.get("from_email") or creds.get("smtp_user")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))

    host = creds.get("smtp_host", "smtp.gmail.com")
    port = int(creds.get("smtp_port", 587) or 587)
    server = smtplib.SMTP(host, port, timeout=25)
    try:
        server.ehlo()
        server.starttls()
        server.login(creds["smtp_user"], creds["smtp_password"])
        server.sendmail(from_email, [to_email], msg.as_string())
        return True, "sent"
    finally:
        server.quit()


async def send_email(creds: dict, to_email: str, subject: str, body: str, html_body: str = ""):
    return await asyncio.to_thread(_send_smtp, creds, to_email, subject, body, html_body)


# ---------------- CRM sync (HubSpot / Zoho) ----------------
def _hubspot_contacts(token):
    r = requests.get(
        "https://api.hubapi.com/crm/v3/objects/contacts",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 50, "properties": "email,firstname,lastname,company,jobtitle,industry"},
        timeout=20,
    )
    r.raise_for_status()
    out = []
    for c in r.json().get("results", []):
        p = c.get("properties", {})
        name = f"{p.get('firstname','') or ''} {p.get('lastname','') or ''}".strip()
        if not (name or p.get("email")):
            continue
        out.append({
            "name": name or (p.get("email", "").split("@")[0] or "Unknown"),
            "email": p.get("email", ""), "company": p.get("company", "") or "Unknown",
            "role": p.get("jobtitle", ""), "industry": p.get("industry", ""),
            "company_size": "", "budget": "", "source": "HubSpot", "notes": "Synced from HubSpot CRM",
        })
    return out


def _zoho_leads(client_id, client_secret, refresh_token):
    tok = requests.post("https://accounts.zoho.com/oauth/v2/token", params={
        "refresh_token": refresh_token, "client_id": client_id,
        "client_secret": client_secret, "grant_type": "refresh_token",
    }, timeout=20)
    access = tok.json().get("access_token")
    if not access:
        raise RuntimeError("Zoho token refresh failed")
    r = requests.get("https://www.zohoapis.com/crm/v2/Leads",
                     headers={"Authorization": f"Zoho-oauthtoken {access}"}, timeout=20)
    if r.status_code == 204:
        return []
    r.raise_for_status()
    out = []
    for l in r.json().get("data", []):
        name = f"{l.get('First_Name','') or ''} {l.get('Last_Name','') or ''}".strip()
        out.append({
            "name": name or l.get("Full_Name", "Unknown"), "email": l.get("Email", "") or "",
            "company": l.get("Company", "") or "Unknown", "role": l.get("Designation", "") or "",
            "industry": l.get("Industry", "") or "", "company_size": "", "budget": "",
            "source": "Zoho", "notes": "Synced from Zoho CRM",
        })
    return out


async def crm_sync(provider: str, creds: dict) -> list:
    if provider == "hubspot":
        return await asyncio.to_thread(_hubspot_contacts, creds["access_token"])
    if provider == "zoho":
        return await asyncio.to_thread(_zoho_leads, creds["client_id"], creds["client_secret"], creds["refresh_token"])
    raise RuntimeError("Unsupported CRM provider")


# ---------------- Social publish (LinkedIn / Meta) ----------------
def _linkedin_post(access_token, author_urn, text):
    body = {
        "author": author_urn, "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": {
            "shareCommentary": {"text": text}, "shareMediaCategory": "NONE"}},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    r = requests.post("https://api.linkedin.com/v2/ugcPosts",
                      headers={"Authorization": f"Bearer {access_token}",
                               "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"},
                      json=body, timeout=20)
    return r.status_code in (200, 201), (r.headers.get("x-restli-id") or r.text)


def _meta_post(page_id, page_token, text):
    r = requests.post(f"https://graph.facebook.com/v19.0/{page_id}/feed",
                      data={"message": text, "access_token": page_token}, timeout=20)
    ok = r.status_code == 200
    return ok, (r.json().get("id") if ok else r.text)


async def social_publish(provider: str, creds: dict, text: str):
    if provider == "linkedin":
        return await asyncio.to_thread(_linkedin_post, creds["access_token"], creds["author_urn"], text)
    if provider == "meta":
        return await asyncio.to_thread(_meta_post, creds["page_id"], creds["page_access_token"], text)
    raise RuntimeError("Unsupported social provider")


# Map a UI platform name to a vault provider id that can publish.
PLATFORM_PROVIDER = {"LinkedIn": "linkedin", "Facebook": "meta", "Instagram": "meta"}


# ---------------- SMS (Twilio) ----------------
def _send_twilio(sid, token, from_number, to_number, body):
    r = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        auth=(sid, token),
        data={"From": from_number, "To": to_number, "Body": body},
        timeout=20,
    )
    return r.status_code in (200, 201), (r.text[:200] if r.text else str(r.status_code))


async def send_sms(creds: dict, to_number: str, body: str):
    return await asyncio.to_thread(
        _send_twilio, creds["account_sid"], creds["auth_token"], creds["from_number"], to_number, body
    )


# ---------------- Twilio Verify (OTP start/check) ----------------
def _verify_start(sid, token, service_sid, to_number):
    r = requests.post(
        f"https://verify.twilio.com/v2/Services/{service_sid}/Verifications",
        auth=(sid, token),
        data={"To": to_number, "Channel": "sms"},
        timeout=20,
    )
    return r.status_code in (200, 201), (r.text[:200] if r.text else str(r.status_code))


def _verify_check(sid, token, service_sid, to_number, code):
    r = requests.post(
        f"https://verify.twilio.com/v2/Services/{service_sid}/VerificationCheck",
        auth=(sid, token),
        data={"To": to_number, "Code": code},
        timeout=20,
    )
    try:
        approved = r.json().get("status") == "approved"
    except Exception:
        approved = False
    return approved, (r.text[:200] if r.text else str(r.status_code))


async def verify_start(creds: dict, to_number: str):
    return await asyncio.to_thread(_verify_start, creds["account_sid"], creds["auth_token"], creds["verify_service_sid"], to_number)


async def verify_check(creds: dict, to_number: str, code: str):
    return await asyncio.to_thread(_verify_check, creds["account_sid"], creds["auth_token"], creds["verify_service_sid"], to_number, code)
