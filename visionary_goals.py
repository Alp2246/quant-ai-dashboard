"""
visionary_goals.py - Sirketlerin "Buyuk Vizyon" hedeflerini takip et.

Algoritma:
  - milestones.json'dan her hisse icin north-star metrik + anahtar kelimeler
  - Haber akisinda 'achievement_patterns' bulunursa: +Vision Bonus
  - 'delay_patterns' bulunursa: -Vision Bonus
  - Net Vision Bonus -15 ile +20 arasinda. Master Score'a eklenir.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from config import BASE_DIR

logger = logging.getLogger(__name__)

VISION_FILE = BASE_DIR / "milestones.json"

ACHIEVEMENT_POINTS = 5      # her eslesme +5 (max +20)
DELAY_POINTS = -5           # her eslesme -5 (min -15)
MAX_BONUS = 20
MIN_BONUS = -15


@lru_cache(maxsize=1)
def _load_db() -> dict:
    try:
        with open(VISION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("milestones.json yuklenemedi: %s", e)
        return {}


def get_vision(ticker: str) -> dict | None:
    """Hisse icin Visionary Goal kaydi dondurur (yoksa None)."""
    db = _load_db()
    return db.get(ticker.upper())


def list_companies() -> list[str]:
    return list(_load_db().keys())


def _match_any(text: str, patterns: list[str]) -> list[tuple[str, str]]:
    """Verilen pattern listesini metin uzerinde ara, eslesmeleri dondur."""
    out = []
    low = text.lower() if text else ""
    for p in patterns or []:
        try:
            m = re.search(p, low, re.IGNORECASE)
            if m:
                out.append((p, m.group(0)))
        except re.error as e:
            logger.debug("Regex hatasi %r: %s", p, e)
    return out


def scan_vision(ticker: str, news_items: list[dict] | None = None) -> dict:
    """
    Haberlerde vizyon hedeflerinin gerceklesip gerceklesmedigini tara.

    Returns:
      {
        ticker, has_vision, vision: {...},
        achievements: [...],   # her biri {title, pattern, snippet, url}
        delays:       [...],
        vision_bonus: -15..+20,
        rating:       'ATILIM' | 'ILERLEME' | 'NOTR' | 'GECIKME' | 'KRIZ'
      }
    """
    vision = get_vision(ticker)
    if not vision:
        return {
            "ticker": ticker, "has_vision": False, "vision": None,
            "achievements": [], "delays": [],
            "vision_bonus": 0, "rating": "VIZYON YOK",
        }

    ach_patterns = vision.get("achievement_patterns", [])
    delay_patterns = vision.get("delay_patterns", [])
    keywords = [k.lower() for k in vision.get("keywords", [])]

    achievements = []
    delays = []
    keyword_hits = []

    for item in news_items or []:
        title = item.get("title", "") or ""
        summary = item.get("summary", "") or ""
        text = f"{title} {summary}"
        link = item.get("link", "")

        for _, snip in _match_any(text, ach_patterns):
            achievements.append({
                "title": title[:160], "pattern_match": snip,
                "url": link, "source": item.get("source", ""),
            })
            break  # ayni haber 1 kez sayilsin

        for _, snip in _match_any(text, delay_patterns):
            delays.append({
                "title": title[:160], "pattern_match": snip,
                "url": link, "source": item.get("source", ""),
            })
            break

        # Sadece anahtar kelime varlik tespiti (Master Score'a etki etmez,
        # ama UI'da gostermek icin)
        low = text.lower()
        for kw in keywords:
            if kw in low:
                keyword_hits.append({
                    "keyword": kw, "title": title[:160],
                    "url": link, "source": item.get("source", ""),
                })
                break

    n_ach = len(achievements)
    n_del = len(delays)
    raw = n_ach * ACHIEVEMENT_POINTS + n_del * DELAY_POINTS
    bonus = max(MIN_BONUS, min(MAX_BONUS, raw))

    # Rating
    if bonus >= 15:
        rating = "ATILIM"      # hedefe ulasildi
    elif bonus >= 5:
        rating = "ILERLEME"    # iyi gidiyor
    elif bonus >= -4:
        rating = "NOTR"        # haber yok
    elif bonus >= -10:
        rating = "GECIKME"     # stratejik gecikme uyarisi
    else:
        rating = "KRIZ"        # ciddi sorun

    # Vizyon mesaji
    if rating == "ATILIM":
        message = f"Vizyona ulasildi: {n_ach} pozitif sinyal yakalandi."
    elif rating == "ILERLEME":
        message = f"Vizyon yolunda: {n_ach} pozitif, {n_del} negatif sinyal."
    elif rating == "GECIKME":
        message = f"⚠️ Stratejik Gecikme Riski: {n_del} gecikme sinyali."
    elif rating == "KRIZ":
        message = f"🚨 Vizyon Krizi: {n_del} ciddi gecikme/sorun haberi."
    else:
        message = "Vizyon hedefi ile ilgili guncel haber yok."

    return {
        "ticker": ticker,
        "has_vision": True,
        "vision": vision,
        "achievements": achievements,
        "delays": delays,
        "keyword_hits": keyword_hits,
        "vision_bonus": bonus,
        "rating": rating,
        "message": message,
        "n_achievements": n_ach,
        "n_delays": n_del,
    }


def critical_news_weight(ticker: str, news_items: list[dict]) -> dict:
    """
    EUV/SMIC ozel agirligi (ASML ve 0981.HK icin).
    Cin-ABD tekno savasi haberleri Master Score'un 'Haber' kismina
    +/- ek agirlik koyar.
    """
    if ticker not in ("ASML", "0981.HK"):
        return {"weight": 0, "context": []}

    positive_terms = [
        ("high-na euv delivery", +3),
        ("euv order record", +3),
        ("license granted", +2),
        ("export approval", +2),
    ]
    negative_terms = [
        ("euv ban", -4),
        ("export control tighter", -3),
        ("new restriction", -3),
        ("license revoked", -4),
        ("entity list", -4),
        ("sanction expand", -3),
    ]

    weight = 0
    context = []
    for item in news_items or []:
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        for term, pts in positive_terms + negative_terms:
            if term in text:
                weight += pts
                context.append({"term": term, "pts": pts,
                                 "title": item.get("title", "")[:140]})
                break
    weight = max(-10, min(+10, weight))
    return {"weight": weight, "context": context}
