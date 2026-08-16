"""SEO & Keyword Intelligence module (Roadmap Module D).

Implements an autonomous organic acquisition engine:
- FR-D01: crawl the customer website and produce technical SEO findings
- FR-D02: discover keywords from seed terms, competitors, search intent and content gaps
- FR-D03: cluster keywords by topic and intent
- FR-D04: score keywords using demand, commercial intent, ranking feasibility,
  competition and predicted conversion value
- FR-D05: generate content briefs, internal-link plans and schema recommendations
- FR-D06: recommend content refreshes
- FR-D07: connect keywords to business outcomes (lead -> revenue attribution hook
  through campaign memory: winning keywords are written back to brain ingestion)
"""

import asyncio
import logging
import re
import urllib.parse

import requests
from bs4 import BeautifulSoup

import ai

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NexusBot/1.0)"}


# ---------------- crawl helpers ----------------

def _fetch_sync(url: str) -> str:
    r = requests.get(url, timeout=20, headers=HEADERS)
    r.raise_for_status()
    return r.text


async def fetch_html(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    return await asyncio.to_thread(_fetch_sync, url)


def collect_internal_links(soup: BeautifulSoup, base_domain: str, max_links: int = 30) -> list:
    """Collect internal links for a lightweight crawl graph (content-gap coverage)."""
    seen, links = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        try:
            parsed = urllib.parse.urlparse(href)
        except ValueError:
            continue
        host = parsed.hostname or ""
        if not host.endswith(base_domain) and base_domain not in host:
            continue
        if parsed.path in seen:
            continue
        seen.add(parsed.path)
        links.append({"url": urllib.parse.urlunparse(parsed), "anchor": (a.get_text() or "").strip()[:100]})
        if len(links) >= max_links:
            break
    return links


def audit_page(html: str, url: str) -> dict:
    """FR-D01: technical SEO findings for a single page."""
    soup = BeautifulSoup(html, "lxml")

    title = (soup.title.string or "").strip() if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = (desc_tag.get("content") or "").strip() if desc_tag else ""
    canonical = ""
    c = soup.find("link", rel="canonical")
    if c:
        canonical = (c.get("href") or "").strip()

    head = soup.find("head") or soup
    schema_types = [s.get("type") or s.get("@type") or "" for s in head.find_all("script", attrs={"type": "application/ld+json"})]

    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    headings = [h.name + ": " + h.get_text(strip=True)[:80] for h in soup.find_all(["h1", "h2", "h3"])][:10]

    images = soup.find_all("img")
    imgs_missing_alt = sum(1 for i in images if not (i.get("alt") or "").strip())

    text = " ".join(soup.get_text(separator=" ").split())
    word_count = len(text.split())

    issues, strengths = [], []

    if not title:
        issues.append("Missing page title tag")
    elif len(title) > 60:
        issues.append(f"Title too long ({len(title)} chars, target <= 60)")
    else:
        strengths.append("Title tag present and within length target")
    if not description:
        issues.append("Missing meta description")
    elif len(description) > 160:
        issues.append(f"Meta description too long ({len(description)} chars, target <= 160)")
    else:
        strengths.append("Meta description present and within length target")
    if len(h1s) == 0:
        issues.append("No H1 heading")
    elif len(h1s) > 1:
        issues.append(f"Multiple H1 headings ({len(h1s)})")
    else:
        strengths.append("Single H1 present")
    if not canonical:
        issues.append("Missing canonical link")
    if not schema_types:
        issues.append("No structured data (schema.org) detected")
    else:
        strengths.append(f"Structured data found: {', '.join(schema_types)}")
    if len(images) > 0 and imgs_missing_alt == len(images):
        issues.append("All images missing alt attributes")
    elif imgs_missing_alt:
        issues.append(f"{imgs_missing_alt} image(s) missing alt attributes")
    if word_count < 300:
        issues.append(f"Thin content ({word_count} words)")
    if word_count >= 600:
        strengths.append(f"Content depth is good ({word_count} words)")

    return {
        "url": url,
        "title": title,
        "meta_description": description,
        "word_count": word_count,
        "headings": headings,
        "canonical": canonical,
        "schema": schema_types,
        "images_total": len(images),
        "images_missing_alt": imgs_missing_alt,
        "issues": issues,
        "strengths": strengths,
    }


async def crawl_tech_seo(site_url: str) -> dict:
    """FR-D01: crawl site, audit core pages, report aggregate technical findings."""
    html = await fetch_html(site_url)
    soup = BeautifulSoup(html, "lxml")
    domain = urllib.parse.urlparse(site_url).hostname or site_url
    domain = re.sub(r"^www\.", "", domain)

    pages = [{"url": site_url, "html": html}]

    for link in collect_internal_links(soup, domain, 15):
        try:
            child_html = await fetch_html(link["url"])
            pages.append({"url": link["url"], "html": child_html})
        except Exception as e:  # noqa: BLE001
            logger.warning("crawl child failed: %s %s", link["url"], e)

    audits = []
    for p in pages[:10]:
        audits.append(audit_page(p["html"], p["url"]))

    issue_counts: dict = {}
    for a in audits:
        for i in a["issues"]:
            key = i.split("(")[0].strip()
            issue_counts[key] = issue_counts.get(key, 0) + 1

    return {
        "site": site_url,
        "pages_audited": len(audits),
        "audits": audits,
        "recurring_issues": [{"issue": k, "pages_affected": v} for k, v in sorted(issue_counts.items(), key=lambda kv: -kv[1])],
        "score": max(40, 100 - sum(v * 8 for v in issue_counts.values())),
    }


# ---------------- keyword intelligence ----------------

async def discover_keywords(seeds: list, industry: str, competitors: list, product_context: str) -> dict:
    """FR-D02 + D03 + D04: keyword discovery, clustering, scoring — all grounded in
    the business context so recommendations connect keywords to revenue outcomes."""
    system = (
        "You are a senior SEO and demand-generation strategist. You research keywords "
        "that drive qualified pipeline and revenue, not vanity search volume."
    )
    competitors_block = "\n".join(f"- {c.get('name', c)} ({c.get('url', '')})" for c in competitors) if competitors else "- (none provided)"
    prompt = f"""Business context:
Industry: {industry}
Product/offer: {product_context}
Competitors:
{competitors_block}

Seed keywords: {', '.join(seeds)}

Research and return JSON:
{{
  "keywords": [
    {{
      "keyword": "exact keyword phrase",
      "topic_cluster": "topic cluster name",
      "search_intent": "informational|commercial|transactional|navigational",
      "demand": "high|medium|low (search demand estimate)",
      "commercial_intent": 0.0 to 1.0,
      "competition": "high|medium|low (ranking difficulty)",
      "ranking_feasibility": 0.0 to 1.0,
      "predicted_conversion_value": 0.0 to 1.0,
      "priority_score": 0.0 to 1.0,
      "recommended_content_type": "blog|landing page|product page|comparison|guide",
      "funnel_stage": "top|middle|bottom",
      "why": "1-sentence justification tied to this business's revenue goals"
    }}
  ],
  "content_gaps": ["topics competitors cover that are missing or weak for this business"],
  "cluster_summary": {{
    "clusters": [{{"name": "", "keyword_count": 0, "priority": "high|medium|low", "revenue_potential": "1-sentence"}}]
  }}
}}
Return 15-25 keywords. The priority_score must weigh commercial intent, feasibility and conversion value together."""
    result = await ai.generate_json("seo-keywords", system, prompt)
    return result


async def keyword_briefs(keywords: list, industry: str, product_context: str) -> dict:
    """FR-D05: content briefs, internal-link plan and schema recommendations for the top clusters."""
    system = "You are an SEO content strategist producing execution-ready briefs."
    kw_block = "\n".join(
        f"- {k.get('keyword','')} | {k.get('topic_cluster','')} | {k.get('search_intent','')} | {k.get('funnel_stage','')}"
        for k in keywords[:12]
    )
    prompt = f"""Industry: {industry}
Product/offer: {product_context}

Keywords to brief:
{kw_block}

Return JSON:
{{
  "briefs": [
    {{
      "keyword": "",
      "working_title": "",
      "target_intent": "",
      "outline": ["section 1","section 2","section 3","section 4","section 5"],
      "primary_keyword": "",
      "secondary_keywords": ["k1","k2","k3"],
      "internal_link_plan": ["link to /... about ..."],
      "schema_recommendation": "Article|FAQPage|Product|SoftwareApplication|None + short reason",
      "refresh_plan": "cadence or condition for refreshing (e.g. quarterly, after ranking drop)",
      "expected_outcome": "1 sentence on pipeline/revenue impact"
    }}
  ],
  "site_architecture_notes": ["1-3 notes on internal linking structure for these clusters"]
}}"""
    return await ai.generate_json("seo-briefs", system, prompt)
