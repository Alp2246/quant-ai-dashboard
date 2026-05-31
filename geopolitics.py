"""
geopolitics.py - ABD ihracat kontrolu (BIS) + Cin ihracat lisansi (MOFCOM)
takibi. Yari iletken sektorunde 'Supply Chain Risk' tespit eder.

Veri kaynaklari:
  1) US BIS Federal Register RSS (federalregister.gov)
  2) Google News RSS - filtreli sorgular
  3) (opsiyonel) MOFCOM duyurulari (Mandarin, simdilik haber RSS uzerinden)

Risk seviyeleri: GUVENLI / IZLE / DIKKAT / KIRMIZI ALARM
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser

logger = logging.getLogger(__name__)


# Hisse -> izlenecek anahtar terimler (ihracat kisitlamasi yon riski)
GEO_KEYWORDS = {
    "AXTI": [
        "Indium Phosphide export control",
        "Gallium Arsenide export license China",
        "InP wafer sanctions",
        "gallium export license China 2026",
        "germanium export restriction MOFCOM",
    ],
    "NVTS": [
        "gallium nitride export control",
        "GaN substrate China license",
        "Navitas China export ban",
    ],
    "INDI": [
        "indie semiconductor automotive chip sanctions",
        "China auto chip export control",
    ],
    "0981.HK": [
        "SMIC export restrictions BIS",
        "SMIC entity list 2026",
        "China 7nm sanctions",
    ],
    "1347.HK": [
        "Hua Hong export control",
        "China mature node restrictions",
    ],
    "ASML": [
        "ASML EUV export ban China",
        "ASML High-NA delivery restriction",
        "Netherlands semiconductor export 2026",
    ],
    "NVDA": [
        "NVIDIA H200 China ban",
        "AI chip export restriction Commerce",
    ],
    "WOLF": [
        "Wolfspeed export license",
        "SiC sanctions",
        "silicon carbide China export restrict",
    ],
    "ATOM": [
        "Atomera licensing restriction",
    ],
    "IONQ": [
        "quantum technology export control",
    ],
    # Yeni AI/Quantum sepeti
    "QBTS": ["D-Wave quantum export control"],
    "RGTI": ["Rigetti quantum export restriction"],
    "POET": ["POET silicon photonics export"],
    "MU":   ["Micron HBM China export"],
    "ARM":  ["ARM China license"],
    "SMCI": ["Super Micro server export control"],
    "PLTR": ["Palantir government export"],
}

# Pozitif (riski azaltir) vs Negatif (riski artirir) pattern'ler
NEGATIVE_PATTERNS = [
    r"\b(export\s+ban|export\s+restrict|export\s+control)\b",
    r"\b(entity\s+list)\b",
    r"\b(license\s+denied|license\s+required)\b",
    r"\b(sanction)\b",
    r"\b(supply\s+chain\s+disrupt)\b",
    r"\b(tariff\s+(impose|increase|raise))\b",
    r"\b(quota)\b",
    r"\b(critical\s+mineral)\b",
    # Bidirectional gallium/germanium patterns (ham madde ihracati)
    r"\bgallium\s+(export|exports|restrict|sanction|ban|license)",
    r"\bgermanium\s+(export|exports|restrict|sanction|ban|license)",
    r"\bexport\s+license\s+(requir|on)\s+(\w+\s+){0,4}(gallium|germanium|indium|graphite)",
    r"\b(restrict|control|ban|tighten)\s+(\w+\s+){0,4}(gallium|germanium|indium)\s+exports",
    r"\b(rare\s+earth\s+(ban|restrict))\b",
]

# KRITIK EXPORT MALZEMELERI - Ga/Ge/InP/GaAs/EUV/AI chip
# Bunlar haberi gelirse Master Score'dan -15 (geo_w 'CRITICAL' bandi).
CRITICAL_EXPORT_KEYWORDS = [
    r"\bgallium\b", r"\bgermanium\b", r"\bindium\s+phosphide\b",
    r"\bInP\b", r"\bGaAs\b",
    r"\bEUV\s+lithography\b", r"\bAI\s+chip\s+export\b",
    r"\bsilicon\s+carbide\s+(export|restrict|sanction)",
]

CRITICAL_TRIGGER_VERBS = [
    r"\b(impose|tighten|restrict|ban|require|expand)\b",
    r"\b(export\s+license|export\s+control|export\s+restriction)\b",
    r"\b(sanction|entity\s+list|denied)\b",
]
POSITIVE_PATTERNS = [
    r"\b(license\s+(granted|approved|issued))\b",
    r"\b(restrictions?\s+(lift|ease|relax|remove))\b",
    r"\b(trade\s+(deal|agreement))\b",
    r"\b(detente|thaw|reconcile)\b",
    r"\b(waiver|exemption)\b",
]


def fetch_bis_federal_register() -> list[dict]:
    """US Federal Register'da BIS (Bureau of Industry and Security) duyurulari."""
    url = ("https://www.federalregister.gov/documents/search.rss?"
           "conditions[agencies][]=industry-and-security-bureau&"
           "conditions[type][]=NOTICE&conditions[type][]=RULE")
    items = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:15]:
            items.append({
                "title": e.get("title", ""),
                "summary": re.sub(r"<[^>]+>", "", e.get("summary", ""))[:300],
                "published": e.get("published", ""),
                "link": e.get("link", ""),
                "source": "federal_register_bis",
            })
    except Exception as e:
        logger.warning("BIS Federal Register hata: %s", e)
    return items


def fetch_geo_news(query: str, limit: int = 6) -> list[dict]:
    """Google News RSS jeopolitik filtre."""
    url = (f"https://news.google.com/rss/search?"
           f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en")
    items = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:limit]:
            items.append({
                "title": e.get("title", ""),
                "summary": re.sub(r"<[^>]+>", "", e.get("summary", ""))[:300],
                "published": e.get("published", ""),
                "link": e.get("link", ""),
                "source": "google_news_geo",
            })
    except Exception as e:
        logger.debug("geo news %s hata: %s", query, e)
    return items


def _score_text(text: str) -> int:
    """Negative pattern -> -1, positive -> +1, none -> 0."""
    t = text.lower()
    if any(re.search(p, t) for p in NEGATIVE_PATTERNS):
        return -1
    if any(re.search(p, t) for p in POSITIVE_PATTERNS):
        return +1
    return 0


def _detect_critical_export(text: str) -> bool:
    """
    Ga/Ge/InP/GaAs/EUV/SiC gibi KRITIK malzemeler + restriction fiili icermesi
    gerekir. Master Score'dan -15 puan tetikler.
    """
    t = text.lower()
    has_keyword = any(re.search(p, t, re.IGNORECASE)
                       for p in CRITICAL_EXPORT_KEYWORDS)
    has_verb = any(re.search(p, t, re.IGNORECASE)
                    for p in CRITICAL_TRIGGER_VERBS)
    return has_keyword and has_verb


def assess_ticker(ticker: str, include_bis: bool = True) -> dict:
    """
    Bir hisse icin jeopolitik risk degerlendirmesi.

    Returns:
      {
        ticker, risk_score (-10..+10),
        risk_level: 'GUVENLI'|'IZLE'|'DIKKAT'|'KIRMIZI ALARM',
        critical_alert: bool,
        negative_items[], positive_items[],
        export_weight (-10..+10) -> Master Score'a modifier
      }
    """
    keywords = GEO_KEYWORDS.get(ticker, [])
    neg_items, pos_items = [], []
    raw_score = 0
    critical_export_hit = False  # Ga/Ge/InP/EUV/SiC KIRMIZI ALARM

    for kw in keywords:
        for item in fetch_geo_news(kw, limit=5):
            text = item["title"] + " " + item["summary"]
            s = _score_text(text)
            if s < 0:
                neg_items.append(item)
                raw_score -= 1
            elif s > 0:
                pos_items.append(item)
                raw_score += 1
            # KRITIK ihracat malzemesi tetikleyicisi
            if _detect_critical_export(text):
                critical_export_hit = True
                item["critical_export"] = True
                if item not in neg_items:
                    neg_items.append(item)

    # BIS Federal Register (US tarafi resmi duyurular)
    if include_bis:
        for item in fetch_bis_federal_register():
            text = item["title"] + " " + item["summary"]
            # Sirket ismi eslesirse +0.5 katsayi
            ticker_l = ticker.lower().replace(".hk", "").replace(".tw", "")
            if (ticker_l in text.lower() or
                any(k.split()[0].lower() in text.lower() for k in keywords)):
                s = _score_text(text)
                if s < 0:
                    raw_score -= 2  # resmi -> daha agir
                    neg_items.append({**item, "weight": "OFFICIAL"})
                elif s > 0:
                    raw_score += 2
                    pos_items.append({**item, "weight": "OFFICIAL"})

    risk = max(-10, min(10, raw_score))
    # KRITIK Ga/Ge ihracat tetigi -> ekstra -5 (toplam -15 tavanina ulasir)
    if critical_export_hit:
        risk -= 5
        risk = max(-15, risk)   # CRITICAL EXPORT FILTER tavani -15
    # Negatif risk yuksek -> level kotu
    if risk <= -10:
        level = "🚨🚨 KIRMIZI ALARM (CRITICAL EXPORT)"
        critical = True
    elif risk <= -5:
        level = "🚨 KIRMIZI ALARM"
        critical = True
    elif risk <= -2:
        level = "⚠️ DIKKAT"
        critical = False
    elif risk <= -1:
        level = "📡 IZLE"
        critical = False
    elif risk <= 1:
        level = "✅ GUVENLI"
        critical = False
    else:
        level = "🟢 OLUMLU GELISME"
        critical = False

    return {
        "ticker": ticker,
        "risk_score": risk,
        "risk_level": level,
        "critical_alert": critical,
        "critical_export_block": critical_export_hit,
        "negative_items": neg_items[:5],
        "positive_items": pos_items[:3],
        "n_negative": len(neg_items),
        "n_positive": len(pos_items),
        # negatif risk -> Master'a negatif modifier (-15..+10)
        "export_weight": -risk,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
