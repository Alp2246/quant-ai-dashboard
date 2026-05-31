"""
capex_watch.py - Buyuk dokumhanelerin (TSMC, Samsung, Intel) yatirim
duyurularini takip et. Pozitif sinyal: capex artisi/yeni fab -> ASML/WOLF
tedarikciler icin pozitif. Negatif: capex cut -> tedarikciler icin negatif.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

import feedparser

logger = logging.getLogger(__name__)

# Takip edilen 'tetikleyici' sirketler
FOUNDRY_GIANTS = {
    "TSM":    "Taiwan Semiconductor TSMC",
    "INTC":   "Intel Corporation foundry IFS",
    "005930.KS": "Samsung Electronics foundry",
    "NVDA":   "NVIDIA AI chip",
    "AMD":    "Advanced Micro Devices",
    "MU":     "Micron Technology memory",
}

# Sektorel etki haritasi: tetikleyici -> etkilenen
# pozitif = tetikleyici iyi giderse etkilenen iyi gider
IMPACT_MAP = {
    "TSM": {
        "ASML": +1.0,    # TSMC capex -> ASML siparis
        "WOLF": +0.5,    # SiC EV gucu
        "ATOM": +0.7,    # MST lisanslama umudu
        "0981.HK": -0.5, # rakip Cin SMIC
        "AXTI": +0.4,
    },
    "INTC": {
        "ASML": +0.9,    # Intel 18A High-NA EUV alimi
        "ATOM": +0.6,    # MST potansiyel musteri
        "WOLF": +0.3,
    },
    "005930.KS": {
        "ASML": +0.8,
        "ATOM": +0.5,
        "WOLF": +0.3,
    },
    "NVDA": {
        "ASML": +0.6,    # NVDA AI talep -> TSMC -> ASML
        "WOLF": +0.4,    # AI guc kaynaklari
        "NVTS": +0.5,    # GaN data center
        "INDI": +0.3,
        "IONQ": +0.3,    # hibrit AI+kuantum hype
    },
    "AMD": {
        "ASML": +0.4, "ATOM": +0.3, "NVTS": +0.3,
    },
    "MU": {"ASML": +0.4, "0981.HK": +0.3},
}

# Capex pozitif/negatif keyword'leri
POSITIVE_PATTERNS = [
    r"raise[sd]?\s+capex",
    r"capex\s+(increase|raise|expansion|boost)",
    r"new\s+fab\s+(announce|open|build)",
    r"capacity\s+(expansion|increase)",
    r"record\s+(order|backlog)",
    r"foundry\s+investment",
    r"\$\d+\s*billion\s+(invest|expansion|fab)",
    r"design\s+win",
]
NEGATIVE_PATTERNS = [
    r"cut\s+capex",
    r"capex\s+(cut|reduce|delay|postpone)",
    r"fab\s+(delay|postpone|cancel)",
    r"order\s+(cut|decline|cancel)",
    r"layoff",
    r"production\s+(halt|delay|suspend)",
    r"revenue\s+(miss|warn)",
    r"guidance\s+(cut|lower|miss)",
]


def fetch_giant_news(ticker: str, limit: int = 8) -> list[dict]:
    """Bir foundry/cip devi icin Google News RSS."""
    name = FOUNDRY_GIANTS.get(ticker, ticker)
    query = f"{ticker} OR {name} capex OR investment OR fab"
    url = (f"https://news.google.com/rss/search?"
           f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en")
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            title = entry.get("title", "")
            summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))
            items.append({
                "title": title,
                "summary": summary[:300],
                "published": entry.get("published", ""),
                "link": entry.get("link", ""),
                "source": "google_news_capex",
            })
    except Exception as e:
        logger.warning("capex RSS hata (%s): %s", ticker, e)
    return items


def score_capex_news(news_items: list[dict]) -> dict:
    """Pozitif/negatif pattern eslesmesi -> capex sinyali."""
    pos_hits = []
    neg_hits = []
    for item in news_items or []:
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        for pat in POSITIVE_PATTERNS:
            if re.search(pat, text):
                pos_hits.append({"pattern": pat, "title": item.get("title", "")[:140]})
                break
        else:
            for pat in NEGATIVE_PATTERNS:
                if re.search(pat, text):
                    neg_hits.append({"pattern": pat, "title": item.get("title", "")[:140]})
                    break

    n_pos = len(pos_hits)
    n_neg = len(neg_hits)
    # Net capex sinyali -10..+10
    raw = n_pos - n_neg
    signal = max(-10, min(10, raw * 2))
    return {
        "positive_hits": pos_hits,
        "negative_hits": neg_hits,
        "n_positive": n_pos,
        "n_negative": n_neg,
        "signal": signal,
    }


def scan_sector(giants: list[str] | None = None) -> dict:
    """Tum foundry devleri taranir, her biri icin pos/neg sinyal."""
    giants = giants or list(FOUNDRY_GIANTS.keys())
    result = {}
    for g in giants:
        news = fetch_giant_news(g, limit=6)
        score = score_capex_news(news)
        result[g] = {
            "name": FOUNDRY_GIANTS.get(g, g),
            "signal": score["signal"],
            "n_pos": score["n_positive"],
            "n_neg": score["n_negative"],
            "headlines": (score["positive_hits"] + score["negative_hits"])[:5],
        }
    return result


def derive_ticker_capex_weight(ticker: str, sector_scan: dict) -> dict:
    """
    Her hisse icin foundry devlerinden gelen sinyalin agirlikli toplami.
    Cikti -5..+5 (Master Score'a etki edebilir).
    """
    total = 0.0
    contributors = []
    for giant, data in sector_scan.items():
        if giant not in IMPACT_MAP:
            continue
        weight_map = IMPACT_MAP[giant]
        if ticker not in weight_map:
            continue
        coef = weight_map[ticker]
        contribution = data["signal"] * coef * 0.5  # 0.5 olcek faktoru
        total += contribution
        if abs(contribution) >= 0.5:
            contributors.append({
                "source": giant,
                "signal": data["signal"],
                "coef": coef,
                "contribution": round(contribution, 2),
                "headlines": data["headlines"][:2],
            })

    weight = max(-5, min(5, round(total, 2)))
    if weight >= 2:
        label = "🟢 GUCLU TEDARIK ZINCIRI POZITIF"
    elif weight >= 0.5:
        label = "✅ Sektorel Ruzgar Lehte"
    elif weight <= -2:
        label = "🔴 SEKTOREL CAPEX KESINTISI"
    elif weight <= -0.5:
        label = "⚠️ Sektorel Riskler Var"
    else:
        label = "➖ Sektorel Notr"

    return {
        "ticker": ticker,
        "capex_weight": weight,
        "label": label,
        "contributors": contributors,
    }
