import os
from cryptography.fernet import Fernet

_key = os.environ.get("CREDENTIALS_KEY")
_fernet = Fernet(_key.encode()) if _key else None


def encrypt(value: str) -> str:
    if not value:
        return ""
    return _fernet.encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except Exception:
        return ""


def mask(value: str) -> str:
    """Return a masked hint of a decrypted secret, e.g. '••••cd12'."""
    if not value:
        return ""
    if len(value) <= 4:
        return "••••"
    return "••••" + value[-4:]


# Provider catalog for the Integrations / Connections area.
PROVIDERS = [
    {"id": "linkedin", "label": "LinkedIn", "category": "Social Publishing",
     "fields": ["access_token", "author_urn"],
     "help": "LinkedIn access token (w_member_social) + author URN e.g. urn:li:person:xxxx or urn:li:organization:xxxx."},
    {"id": "meta", "label": "Meta (Facebook & Instagram)", "category": "Social Publishing",
     "fields": ["page_id", "page_access_token"],
     "help": "A Facebook Page ID and a long-lived Page access token with pages_manage_posts."},
    {"id": "twitter_x", "label": "X (Twitter)", "category": "Social Publishing",
     "fields": ["api_key", "api_secret", "access_token", "access_secret"],
     "help": "Create an X Developer project with Read+Write access."},
    {"id": "google_ads", "label": "Google Ads", "category": "Ad Platforms",
     "fields": ["developer_token", "client_id", "client_secret", "refresh_token", "customer_id"],
     "help": "Apply for a Google Ads developer token and OAuth client."},
    {"id": "meta_ads", "label": "Meta Ads", "category": "Ad Platforms",
     "fields": ["access_token", "ad_account_id"],
     "help": "Use a Meta Marketing API access token with ads_management scope."},
    {"id": "email", "label": "Email (SMTP)", "category": "Messaging",
     "fields": ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "from_email", "from_name"],
     "help": "Any SMTP server (Gmail, SendGrid, Resend, SES). Gmail uses smtp.gmail.com:587 with an App Password."},
    {"id": "whatsapp", "label": "WhatsApp & SMS (Twilio)", "category": "Messaging",
     "fields": ["account_sid", "auth_token", "from_number"],
     "help": "Twilio account SID + auth token; a WhatsApp-enabled or SMS number."},
    {"id": "twilio_verify", "label": "Twilio Verify (OTP)", "category": "Messaging",
     "fields": ["account_sid", "auth_token", "verify_service_sid"],
     "help": "Twilio Verify service — sends & checks login OTP codes over SMS."},
    {"id": "google_search", "label": "Google Places / Custom Search", "category": "Lead Sources",
     "fields": ["api_key", "search_engine_id"],
     "help": "Enable Places API or Programmable Search Engine and create an API key."},
    {"id": "hubspot", "label": "HubSpot CRM", "category": "Lead Sources",
     "fields": ["access_token"],
     "help": "Create a HubSpot private app token with CRM scopes."},
    {"id": "zoho", "label": "Zoho CRM", "category": "Lead Sources",
     "fields": ["client_id", "client_secret", "refresh_token"],
     "help": "Register a Zoho API client and generate a refresh token."},
    {"id": "salesforce", "label": "Salesforce CRM", "category": "Lead Sources",
     "fields": ["client_id", "client_secret", "username", "password", "security_token"],
     "help": "Create a Salesforce Connected App with API enabled."},
]

PROVIDER_MAP = {p["id"]: p for p in PROVIDERS}
