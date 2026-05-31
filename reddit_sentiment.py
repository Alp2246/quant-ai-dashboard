"""
reddit_sentiment.py - Reddit RSS feeds icin sosyal medya sentiment

Anahtarsiz; reddit.com/r/<sub>/search.rss endpoint'i kullanir.
Subreddit listesi: stocks, QuantumComputing, semiconductors, wallstreetbets, investing
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

import feedparser

from config import COMPANY_NAMES

logger = logging.getLogger(__name__)

SUBREDDITS = [
    "stocks",
    "investing",
    "QuantumComputing",
    "semiconductors",
    "wallstreetbets",
]


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return text.strip()


def fetch_reddit_posts(ticker: str, limit_per_sub: int = 5) -> list[dict]:
    """Tum subreddit'lerden ticker icin son gonderiler."""
    company = COMPANY_NAMES.get(ticker, ticker)
    query = quote_plus(f"{ticker} OR {company.split()[0]}")
    items = []
    for sub in SUBREDDITS:
        url = (
            f"https://www.reddit.com/r/{sub}/search.rss"
            f"?q={query}&restrict_sr=1&sort=new&t=week"
        )
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "QuantBot/1.0"})
            for entry in feed.entries[:limit_per_sub]:
                items.append({
                    "title": entry.get("title", ""),
                    "summary": _clean(entry.get("summary", ""))[:400],
                    "published": entry.get("published", ""),
                    "source": f"r/{sub}",
                    "link": entry.get("link", ""),
                })
        except Exception as e:
            logger.debug("r/%s feed hatasi: %s", sub, e)
    return items


def analyze_reddit_sentiment(ticker: str) -> dict:
    """Reddit gonderilerinden ortalama sentiment."""
    from sentiment_analysis import score_text  # circular import'u onlemek icin lazy

    posts = fetch_reddit_posts(ticker)
    if not posts:
        return {
            "score": 0.0,
            "count": 0,
            "label": "veri yok",
            "posts": [],
        }

    scored = []
    for p in posts:
        text = f"{p['title']} {p['summary']}"
        s = score_text(text)
        scored.append({**p, "sentiment": s})

    avg = sum(p["sentiment"] for p in scored) / len(scored)
    if avg > 0.10:
        label = "pozitif"
    elif avg < -0.10:
        label = "negatif"
    else:
        label = "notr"

    scored.sort(key=lambda x: abs(x["sentiment"]), reverse=True)

    return {
        "score": round(avg, 4),
        "count": len(scored),
        "label": label,
        "posts": scored[:5],   # en etkili 5
    }
