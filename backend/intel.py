import asyncio
import logging
import urllib.parse
import requests
import feedparser
from bs4 import BeautifulSoup
import ai

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NexusBot/1.0)"}


def _fetch_sync(url: str) -> str:
    r = requests.get(url, timeout=20, headers=HEADERS)
    r.raise_for_status()
    return r.text


async def fetch_site_text(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    html = await asyncio.to_thread(_fetch_sync, url)
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = (soup.title.string or "").strip() if soup.title else ""
    text = " ".join(soup.get_text(separator=" ").split())
    return f"PAGE TITLE: {title}\n\nCONTENT:\n{text[:7000]}"


async def analyze_competitor(name: str, url: str) -> dict:
    text = await fetch_site_text(url)
    system = "You are a competitive intelligence analyst. Analyze a competitor's website content objectively."
    prompt = f"""Analyze competitor "{name}" ({url}) based on their website content below.

{text}

Return JSON:
{{
  "positioning": "1-2 sentence market positioning",
  "value_proposition": "their core promise",
  "key_messaging": ["msg1","msg2","msg3"],
  "products": ["product/service 1","2"],
  "pricing_signals": "any pricing/plan info found or 'Not disclosed'",
  "target_audience": "who they target",
  "ctas": ["primary call-to-action seen"],
  "strengths": ["s1","s2"],
  "weaknesses": ["potential gap 1","2"],
  "counter_strategy": "how to win against them"
}}"""
    return await ai.generate_json(f"comp-{name}", system, prompt)


def _fetch_news_sync(query: str):
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    r = requests.get(url, timeout=20, headers=HEADERS)
    return feedparser.parse(r.content)


async def fetch_news(query: str, limit: int = 15) -> list:
    feed = await asyncio.to_thread(_fetch_news_sync, query)
    items = []
    for e in feed.entries[:limit]:
        items.append({
            "title": getattr(e, "title", ""),
            "link": getattr(e, "link", ""),
            "source": getattr(getattr(e, "source", None), "title", "") if hasattr(e, "source") else "",
            "published": getattr(e, "published", ""),
        })
    return items


async def discover_trends(industry: str) -> dict:
    news = await fetch_news(f"{industry} marketing trends", 20)
    headlines = "\n".join(f"- {n['title']} ({n['source']})" for n in news)
    system = "You are a market trend analyst. Extract actionable marketing trends from real news headlines."
    prompt = f"""Based on these REAL recent news headlines about the {industry} industry:

{headlines}

Return JSON:
{{
  "summary": "2-sentence state of trends right now",
  "trending_topics": [{{"topic":"","why_it_matters":""}}],
  "keywords": ["kw1","kw2","kw3","kw4","kw5"],
  "hashtags": ["#h1","#h2","#h3"],
  "sentiment": "Positive|Neutral|Negative + brief reason",
  "content_opportunities": ["idea1","idea2","idea3"]
}}"""
    result = await ai.generate_json(f"trends-{industry}", system, prompt)
    result["sources"] = news[:10]
    return result
