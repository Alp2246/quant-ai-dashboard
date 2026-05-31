"""
patent_watch.py - Google Patents + akademik haber tarayicisi.

ATOM (MST), IONQ (Barium qubit), WOLF (SiC crystallization), ASML (High-NA EUV),
SMIC (7nm DUV) gibi sirketler icin stratejik patent / akademik aktivite takibi.

Google Patents'in resmi API'si yok ama https://patents.google.com/?q=... arama
sayfasini scrape edilebilir. Yedek olarak Google News RSS'i 'patent' kelimesi
ile filtreliyoruz.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# Sirket -> ([anahtar kelimeler]). Bunlar 'stratejik' kabul edilir.
PATENT_KEYWORDS = {
    "ATOM": ["Mears Silicon Technology", "MST band engineering",
             "epitaxial deposition transistor"],
    "IONQ": ["barium qubit", "trapped ion quantum", "algorithmic qubit",
             "error correction logical qubit"],
    "WOLF": ["silicon carbide MOSFET", "SiC wafer crystallization",
             "200mm SiC substrate", "EV power module"],
    "ASML": ["High-NA EUV", "EUV lithography source", "lens module EUV"],
    "RGTI": ["superconducting qubit fab", "Rigetti scalable processor"],
    "0981.HK": ["SMIC 7nm DUV", "advanced node lithography China"],
    "AXTI": ["Indium Phosphide substrate", "Gallium Arsenide wafer"],
    "NVTS": ["GaN power IC", "gallium nitride driver"],
    "LAES": ["secure microcontroller", "post-quantum hardware"],
    "ATOM_extra": [],
}

# 'Stratejik' patent gostergeleri
STRATEGIC_PATTERNS = [
    r"\bUS\s*Patent\s*[Nn]o", r"\bgranted", r"\bawarded.*patent",
    r"\bfiles?\s+patent", r"\bnewly\s+granted", r"\bportfolio\s+expand",
    r"\bjoint\s+development\b", r"\blicensing\s+agreement",
    r"\bcross[- ]license", r"\bIP\s+(deal|license|transfer)",
]


def _fetch_google_patents(query: str, max_items: int = 8,
                            recent_months: int = 12) -> list[dict]:
    """
    Google Patents arama sayfasi (HTML scrape).
    NOT: Patents UI dinamik JS uretiyor; bu yontem sik bozulabilir. Bu nedenle
    feedparser RSS yedegi de var.
    """
    after = (datetime.now().year if recent_months > 6 else
              datetime.now().year - 1)
    url = (f"https://patents.google.com/?q={quote_plus(query)}"
           f"&oq={quote_plus(query)}&after=priority:{after}0101"
           f"&num={max_items}")
    items = []
    try:
        r = requests.get(url, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/119.0.0.0 Safari/537.36")},
            timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # JS-rendered, ama meta etiketleri statik gelebilir
            for art in soup.select("search-result-item")[:max_items]:
                title = art.get("data-result", "")[:200]
                pub_no = art.get("data-pub-num", "")
                if title or pub_no:
                    items.append({
                        "title": title or pub_no,
                        "publication_no": pub_no,
                        "source": "google_patents_html",
                    })
    except Exception as e:
        logger.debug("patents scrape %s hata: %s", query, e)
    return items


def _fetch_news_patent_filter(query: str, max_items: int = 8) -> list[dict]:
    """Google News RSS + 'patent' filtresi."""
    url = (f"https://news.google.com/rss/search?"
           f"q={quote_plus(query + ' patent OR granted OR awarded')}"
           f"&hl=en-US&gl=US&ceid=US:en")
    items = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:max_items]:
            title = e.get("title", "")
            summary = re.sub(r"<[^>]+>", "", e.get("summary", ""))
            items.append({
                "title": title,
                "summary": summary[:240],
                "published": e.get("published", ""),
                "link": e.get("link", ""),
                "source": "google_news_patent",
            })
    except Exception as e:
        logger.debug("news patent %s hata: %s", query, e)
    return items


def _is_strategic(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in STRATEGIC_PATTERNS)


def scan_patents(ticker: str) -> dict:
    """
    Bir sirketin stratejik patent / IP aktivitesini tarar.

    Returns:
      {
        ticker, total_hits, strategic_hits, recent_items[],
        patent_bonus (0..5), label, source_breakdown
      }
    """
    keywords = PATENT_KEYWORDS.get(ticker, [])
    if not keywords:
        # Sirket adi + 'patent' ile temel arama
        keywords = [f"{ticker} semiconductor patent"]

    all_items = []
    strategic = []
    src_count = {"google_patents_html": 0, "google_news_patent": 0}

    for kw in keywords:
        # 1) Patents scrape (best-effort)
        pats = _fetch_google_patents(kw, max_items=5)
        for p in pats:
            src_count["google_patents_html"] += 1
            p["keyword"] = kw
            all_items.append(p)
            strategic.append(p)  # Patents direkt sonuc = stratejik

        # 2) News RSS yedek
        news = _fetch_news_patent_filter(kw, max_items=4)
        for n in news:
            src_count["google_news_patent"] += 1
            n["keyword"] = kw
            all_items.append(n)
            text = n.get("title", "") + " " + n.get("summary", "")
            if _is_strategic(text):
                strategic.append(n)

    # Bonus 0..5: stratejik patent sayisina dayali
    sh = len(strategic)
    if sh >= 5:
        bonus = 5
        label = "🏆 PATENT KALESI"
    elif sh >= 3:
        bonus = 4
        label = "✅ GUCLU IP PORTFOY"
    elif sh >= 2:
        bonus = 3
        label = "📈 IP AKTIF"
    elif sh >= 1:
        bonus = 2
        label = "📝 IP HAREKETI VAR"
    else:
        bonus = 0
        label = "➖ Stratejik IP haberi yok"

    # En guncel 6 stratejik patenti dondur (UI'da goster)
    recent = strategic[:6]

    return {
        "ticker": ticker,
        "total_hits": len(all_items),
        "strategic_hits": sh,
        "patent_bonus": bonus,
        "label": label,
        "recent_items": recent,
        "source_breakdown": src_count,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
