import re
import asyncio
import csv
import io
import logging
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NexusBot/1.0)"}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
BAD_EMAIL_HINTS = ("example.com", "sentry", "wixpress", ".png", ".jpg", ".jpeg", ".gif", ".webp", "@2x", "domain.com", "email.com", "yourdomain")
PREFERRED = ("info@", "contact@", "sales@", "hello@", "support@", "admin@")


def _norm(domain: str) -> str:
    d = domain.strip()
    if not d.startswith("http"):
        d = "https://" + d
    return d


def _fetch(url: str) -> str:
    try:
        r = requests.get(url, timeout=15, headers=HEADERS)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        logger.info(f"fetch fail {url}: {e}")
    return ""


def _scrape_one(domain: str) -> dict:
    base = _norm(domain)
    host = urlparse(base).netloc.replace("www.", "")
    candidates = [base, urljoin(base, "/contact"), urljoin(base, "/contact-us"),
                  urljoin(base, "/about"), urljoin(base, "/about-us")]
    emails, phones, socials = set(), set(), set()
    company = host
    for url in candidates:
        html = _fetch(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        if url == base and soup.title and soup.title.string:
            company = soup.title.string.strip()[:80]
        for m in EMAIL_RE.findall(html):
            ml = m.lower()
            if not any(b in ml for b in BAD_EMAIL_HINTS) and len(m) < 60:
                emails.add(m)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(s in href for s in ("linkedin.com/company", "twitter.com/", "x.com/", "facebook.com/", "instagram.com/")):
                socials.add(href.split("?")[0])
        text_phones = PHONE_RE.findall(soup.get_text(" "))
        for p in text_phones[:3]:
            if 9 <= len(re.sub(r"\D", "", p)) <= 15:
                phones.add(p.strip())

    email_list = sorted(emails, key=lambda e: (0 if any(e.lower().startswith(p) for p in PREFERRED) else 1, e))
    best_email = email_list[0] if email_list else ""
    return {
        "found": bool(email_list or phones or socials),
        "name": (company.split("|")[0].split("-")[0].strip() or host) + " (Web)",
        "email": best_email,
        "company": company.split("|")[0].split("-")[0].strip() or host,
        "role": "",
        "industry": "",
        "company_size": "",
        "budget": "",
        "source": "Web Scrape",
        "website": base,
        "notes": (
            f"Emails: {', '.join(email_list[:5]) or 'none'}. "
            f"Phones: {', '.join(list(phones)[:2]) or 'none'}. "
            f"Social: {', '.join(list(socials)[:3]) or 'none'}."
        ),
    }


async def scrape_domains(domains: list) -> list:
    tasks = [asyncio.to_thread(_scrape_one, d) for d in domains if d.strip()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = []
    for r in results:
        if isinstance(r, dict):
            out.append(r)
    return out


def parse_csv(csv_text: str) -> list:
    leads = []
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    field_map = {
        "name": ["name", "full name", "fullname", "contact", "lead name"],
        "email": ["email", "e-mail", "email address"],
        "company": ["company", "organization", "organisation", "account"],
        "role": ["role", "title", "job title", "position"],
        "industry": ["industry", "sector"],
        "company_size": ["company size", "size", "employees"],
        "budget": ["budget"],
        "source": ["source", "lead source"],
        "notes": ["notes", "comments", "description"],
    }

    def pick(row, keys):
        low = {k.lower().strip(): v for k, v in row.items() if k}
        for k in keys:
            if k in low and low[k]:
                return str(low[k]).strip()
        return ""

    for row in reader:
        name = pick(row, field_map["name"])
        email = pick(row, field_map["email"])
        company = pick(row, field_map["company"])
        if not (name or email or company):
            continue
        leads.append({
            "name": name or (email.split("@")[0] if email else "Unknown"),
            "email": email,
            "company": company or "Unknown",
            "role": pick(row, field_map["role"]),
            "industry": pick(row, field_map["industry"]),
            "company_size": pick(row, field_map["company_size"]),
            "budget": pick(row, field_map["budget"]),
            "source": pick(row, field_map["source"]) or "CSV Import",
            "notes": pick(row, field_map["notes"]),
        })
    return leads
