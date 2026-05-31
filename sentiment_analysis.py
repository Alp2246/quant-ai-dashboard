"""
sentiment_analysis.py - Haber toplama ve duygu analizi (NLP)
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional
from urllib.parse import quote_plus

import feedparser
import requests
from textblob import TextBlob

from config import COMPANY_NAMES
from data_fetcher import fetch_yfinance_news

logger = logging.getLogger(__name__)

# TextBlob icin NLTK verileri (ilk calistirmada indirilir)
_NLTK_READY = False


def _ensure_nltk():
    global _NLTK_READY
    if _NLTK_READY:
        return
    try:
        import nltk
        for pkg in ("punkt", "punkt_tab", "brown"):
            try:
                nltk.data.find(f"tokenizers/{pkg}" if "punkt" in pkg else f"corpora/{pkg}")
            except LookupError:
                nltk.download(pkg, quiet=True)
        _NLTK_READY = True
    except Exception as e:
        logger.warning("NLTK kurulumu atlandi: %s", e)


def score_text(text: str) -> float:
    """TextBlob compound benzeri polarite: -1 .. +1"""
    if not text or not str(text).strip():
        return 0.0
    _ensure_nltk()
    try:
        return float(TextBlob(str(text)).sentiment.polarity)
    except Exception:
        return 0.0


def fetch_google_news_rss(query: str, limit: int = 8) -> list[dict]:
    """API anahtarisiz Google News RSS."""
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            # HTML tag temizle
            summary = re.sub(r"<[^>]+>", "", summary)
            items.append({
                "title": title,
                "summary": summary[:500],
                "published": entry.get("published", ""),
                "source": "google_rss",
                "link": entry.get("link", ""),
            })
    except Exception as e:
        logger.warning("RSS hatasi (%s): %s", query, e)
    return items


def fetch_newsapi(query: str, limit: int = 8) -> list[dict]:
    """NewsAPI (NEWS_API_KEY gerekli)."""
    key = os.getenv("NEWS_API_KEY", "").strip()
    if not key:
        return []
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": limit,
        "apiKey": key,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return [
            {
                "title": a.get("title", ""),
                "summary": a.get("description", ""),
                "published": a.get("publishedAt", ""),
                "source": a.get("source", {}).get("name", "newsapi"),
                "link": a.get("url", ""),
            }
            for a in data.get("articles", [])
        ]
    except Exception as e:
        logger.warning("NewsAPI hatasi: %s", e)
        return []


def collect_news(ticker: str, limit_per_source: int = 6) -> list[dict]:
    """Tum kaynaklardan haber birlestir."""
    company = COMPANY_NAMES.get(ticker, ticker)
    query = f"{ticker} OR {company}"

    seen_titles = set()
    all_news = []

    for source_fn, args in [
        (fetch_yfinance_news, (ticker, limit_per_source)),
        (fetch_google_news_rss, (query, limit_per_source)),
        (fetch_newsapi, (query, limit_per_source)),
    ]:
        for item in source_fn(*args):
            title = item.get("title", "").strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            all_news.append(item)

    return all_news[:20]


def _annotate_critical(news_items: list[dict]) -> list[dict]:
    """Her habere materyal/ihracat/kontrat etiketleri ekle."""
    try:
        from critical_news import annotate_news
        return annotate_news(news_items)
    except Exception:
        return news_items or []


def analyze_news_sentiment(news_items: list[dict]) -> dict:
    """
    Haber listesinden aggregate sentiment.
    Returns: score (-1..1), label, headlines with scores
    """
    if not news_items:
        return {
            "score": 0.0,
            "label": "notr",
            "count": 0,
            "headlines": [],
        }

    scored = []
    for item in news_items:
        text = f"{item.get('title', '')} {item.get('summary', '')}"
        s = score_text(text)
        scored.append({**item, "sentiment": s})

    scores = [h["sentiment"] for h in scored]
    avg = sum(scores) / len(scores)

    if avg > 0.15:
        label = "pozitif"
    elif avg < -0.15:
        label = "negatif"
    else:
        label = "notr"

    # En etkili 5 haber
    scored.sort(key=lambda x: abs(x["sentiment"]), reverse=True)

    return {
        "score": round(avg, 4),
        "label": label,
        "count": len(scored),
        "headlines": scored[:5],
    }


def get_ticker_sentiment(ticker: str) -> dict:
    """
    Birlesik sentiment: haber (yfinance + Google News + NewsAPI) + Reddit
    Agirlik: haber %60, Reddit %40
    + Kritik teknik haber etiketleri (InP, GaAs, SiC, ihracat kontrolu vs.)
    """
    try:
        news = collect_news(ticker)
    except Exception as e:
        logger.warning("News fetch hatasi (%s): %s", ticker, e)
        news = []
    news = _annotate_critical(news)
    news_result = analyze_news_sentiment(news)

    # Reddit (circular import'u onlemek icin lazy)
    try:
        from reddit_sentiment import analyze_reddit_sentiment
        reddit_result = analyze_reddit_sentiment(ticker)
    except Exception as e:
        logger.warning("Reddit sentiment hatasi (%s): %s", ticker, e)
        reddit_result = {"score": 0.0, "count": 0, "label": "yok", "posts": []}

    # Agirlikli ortalama
    n_w, r_w = 0.60, 0.40
    if reddit_result["count"] == 0:
        combined = news_result["score"]
    elif news_result["count"] == 0:
        combined = reddit_result["score"]
    else:
        combined = n_w * news_result["score"] + r_w * reddit_result["score"]

    if combined > 0.15:
        label = "pozitif"
    elif combined < -0.15:
        label = "negatif"
    else:
        label = "notr"

    # Kritik teknik haber ozeti
    try:
        from critical_news import critical_summary
        crit = critical_summary(news)
    except Exception:
        crit = {"total_critical": 0, "categories": [], "examples": {}}

    return {
        "score": round(combined, 4),
        "label": label,
        "count": news_result["count"] + reddit_result["count"],
        "headlines": news_result["headlines"],
        "news_score": news_result["score"],
        "news_count": news_result["count"],
        "news_raw": news,
        "reddit_score": reddit_result["score"],
        "reddit_count": reddit_result["count"],
        "reddit_label": reddit_result["label"],
        "reddit_posts": reddit_result["posts"],
        "critical": crit,
    }
