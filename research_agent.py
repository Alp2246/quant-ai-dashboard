"""
research_agent.py - Deep Research Agent (v7).

Hardware Intelligence Agent'tan FARKLI olarak gunluk (24h) calismaz, her
saat baslangicinda kontrol eder ve cache 4 saatten eski ise yeniden tarar.
Daha agresif/sik tarama hedefi: spesifik vizyon anahtar kelimeleri uzerinde
'Haber Yogunlugu' (news intensity) skoru uretir.

Bu skor Lopez de Prado'nun 'Feature Importance' mantigi ile Master Score'a
DINAMIK bir katsayi olarak girer (yuksek yogunluk = yuksek alpha katkisi).

Cikti:
  - data/research_agent_cache.json
  - milestones.json icindeki ilgili sirketin 'evidence' listesine
    'Confirmed by Web Research' etiketi + intensity + recent_headlines

Kullanim:
  from research_agent import (run_daily_research, get_intensity,
                                  get_dynamic_master_coef)
  data = run_daily_research()       # sadece stale ise calisir
  data = run_daily_research(True)   # force
  coef = get_dynamic_master_coef("IONQ")   # 0.0 .. 1.5
"""
from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import feedparser

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CACHE_FILE = DATA_DIR / "research_agent_cache.json"
MILESTONES_FILE = Path(__file__).parent / "milestones.json"

TTL_HOURS = 4  # 4 saatlik agresif tazeleme (daily basket'in alti)

# =============================================================================
# Anahtar kelime haritasi (V7 promptundaki birebir sorgular)
# =============================================================================
RESEARCH_QUERIES: dict[str, list[str]] = {
    "IONQ": [
        "IONQ AQ 64 roadmap completion",
        "IONQ Barium trap reliability",
        "IONQ enterprise quantum delivery",
    ],
    "WOLF": [
        "Mohawk Valley fab yield percentage",
        "Wolfspeed Silicon Carbide wafer 200mm transition",
        "Wolfspeed EV power module ramp",
    ],
    "ASML": [
        "ASML High-NA EUV shipping status",
        "TSMC 2nm node readiness ASML",
        "ASML 2026 capex outlook",
    ],
    "ATOM": [
        "Atomera MST licensing agreement",
        "Atomera JDA Foundry customer 2026",
    ],
    "RGTI": [
        "Rigetti scalable superconducting roadmap",
        "Rigetti quantum advantage milestone",
    ],
    "LAES": [
        # v8 GLOBAL DERIN ARASTIRMA (kullanici talebi - her sabah tara)
        "NIST PQC standards update 2026",
        "NIST FIPS 203 204 205 finalized post-quantum",
        "SEALSQ NIST PQC chip integration 2026",
        "SEALSQ post-quantum hardware roadmap",
        "SEALSQ secure element design win",
        "SEALSQ QS7001 Common Criteria EAL5 certification",
        "WISeKey SEALSQ Matter Protocol certification",
        "SEALSQ RISC-V secure enclave VaultiTrust",
        "Q-Day quantum threat RSA harvest now decrypt later",
        "CRYSTALS Kyber Dilithium silicon FIPS 203 204",
        "cybersecurity CAPEX IoT spending 2026 forecast",
    ],
    "0981.HK": [
        "SMIC 7nm mass production 2026",
        "SMIC self-sufficiency ratio China",
    ],
    "AXTI": [
        "AXT Indium Phosphide production",
        "AXT Gallium Arsenide demand 2026",
    ],
    "NVTS": [
        # v8 GLOBAL DERIN ARASTIRMA (kullanici talebi - her sabah tara)
        "GaN market share 2026",
        "GaN power semi adoption rate forecast 2026",
        "Navitas GaN power IC adoption",
        "Navitas EV charging design wins",
        "Navitas Tier-1 OEM automotive design win",
        "NVIDIA Blackwell 48V rack power supply",
        "AI data center power consumption growth 2026",
    ],
}

# Pozitif / negatif anahtarlar (intensity skorunu yonlendirir)
BULLISH_PATTERNS = [
    r"\b(achieve|deliver|ship|complete|breakthrough|first|record)\b",
    r"\b(yield\s+(up|increase|improve))\b",
    r"\b(milestone\s+(reached|hit|achieved))\b",
    r"\b(production\s+(ramp|increase|expansion))\b",
    r"\b(design\s+win)\b",
    r"\b(license\s+(granted|approved|signed))\b",
    r"\b(funding\s+(round|raise))\b",
    r"\b(partnership|joint\s+development)\b",
]
BEARISH_PATTERNS = [
    r"\b(delay|postpone|cancel|miss|slip)\b",
    r"\b(yield\s+(down|drop|low|miss))\b",
    r"\b(layoff|cut\s+staff)\b",
    r"\b(investigation|lawsuit|fine)\b",
    r"\b(downgrade|underperform)\b",
    r"\b(supply\s+(disrupt|shortage))\b",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_news(query: str, limit: int = 10) -> list[dict]:
    """Google News RSS - genis sonuc, sonra filtreleyecegiz."""
    url = (f"https://news.google.com/rss/search?"
           f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en")
    items = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:limit]:
            items.append({
                "title": e.get("title", ""),
                "summary": re.sub(r"<[^>]+>", "",
                                   e.get("summary", ""))[:300],
                "published": e.get("published", ""),
                "link": e.get("link", ""),
            })
    except Exception as ex:
        logger.debug("research_agent _fetch_news %s: %s", query, ex)
    return items


def _classify(text: str) -> int:
    """+1 bullish, -1 bearish, 0 neutral."""
    t = text.lower()
    if any(re.search(p, t) for p in BULLISH_PATTERNS):
        return 1
    if any(re.search(p, t) for p in BEARISH_PATTERNS):
        return -1
    return 0


def _is_recent(published: str, days: int = 30) -> bool:
    """Yayin tarihi son N gun icinde mi?"""
    if not published:
        return True
    try:
        # feedparser RFC 2822 formatinda doner
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(published)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt) <= timedelta(days=days)
    except Exception:
        return True


def scan_ticker(ticker: str) -> dict:
    """
    Bir hisse icin tum sorgu setini tara, intensity hesapla.

    Returns:
      {
        ticker, queries_run, total_items, recent_items,
        bullish, bearish, neutral,
        intensity (0..100),
        net_score (-1..+1),
        dynamic_coef (0.5..1.5)   # Master Score icin
        headlines[],              # en son 5 pozitif/etkili
        evidence_tag: 'Confirmed by Web Research',
        scanned_at
      }
    """
    queries = list(RESEARCH_QUERIES.get(ticker, []))

    # Fisher 'Scuttlebutt' yontemini ek olarak uygula (Common Stocks and
    # Uncommon Profits) - Ar-Ge yogun spekulatif hisselerde kulis arastirmasi.
    scuttle = []
    try:
        from sector_tam import get_scuttlebutt_queries
        scuttle = get_scuttlebutt_queries(ticker)
    except Exception:
        scuttle = []
    queries = queries + scuttle

    if not queries:
        return {
            "ticker": ticker, "queries_run": 0, "total_items": 0,
            "recent_items": 0, "bullish": 0, "bearish": 0, "neutral": 0,
            "intensity": 0, "net_score": 0.0, "dynamic_coef": 1.0,
            "headlines": [], "evidence_tag": "Confirmed by Web Research",
            "scanned_at": _now_iso(),
            "note": "Bu hisse icin RESEARCH_QUERIES tanimlanmadi.",
        }

    all_items: list[dict] = []
    bull = bear = neu = 0
    recent_count = 0

    for q in queries:
        for item in _fetch_news(q, limit=8):
            text = (item.get("title", "") + " " + item.get("summary", ""))
            cls = _classify(text)
            item["query"] = q
            item["classification"] = ("bullish" if cls > 0 else
                                        "bearish" if cls < 0 else "neutral")
            recent = _is_recent(item.get("published", ""), days=30)
            item["recent"] = recent
            if recent:
                recent_count += 1
                if cls > 0:
                    bull += 1
                elif cls < 0:
                    bear += 1
                else:
                    neu += 1
            all_items.append(item)

    total = len(all_items)
    # Net score [-1, +1]: pozitif/negatif dengesi
    if (bull + bear) > 0:
        net = (bull - bear) / (bull + bear)
    else:
        net = 0.0

    # Intensity 0..100: son 30 gunde bull+bear haber sayisi (haber yogunlugu)
    raw_int = (bull + bear) * 6 + neu * 2
    intensity = max(0, min(100, raw_int))

    # ---------- Dinamik Master Coef (Lopez de Prado Feature Importance) -----
    # Mantik: 'haber yogunlugu' bir 'feature' olarak Master Score'a girer.
    # Lopez de Prado'nun MDA prensibi: bir feature ne kadar guclu sinyal
    # uretiyorsa o kadar agirligi artar. Burada feature = intensity*net.
    # Coef = 1.0 (notr) + (intensity/100) * net * 0.5
    # Net pozitifse 1.5'e kadar Master Score'u carpar, negatifse 0.5'e dusurur.
    coef = 1.0 + (intensity / 100.0) * net * 0.5
    coef = max(0.5, min(1.5, round(coef, 3)))

    # En etkili 5 headline (oncelik bull/bear, sonra recent)
    sorted_items = sorted(
        all_items,
        key=lambda x: (
            0 if x["classification"] != "neutral" else 1,
            0 if x.get("recent") else 1,
        ),
    )
    headlines = [{
        "title": it["title"][:200],
        "summary": it.get("summary", "")[:200],
        "link": it.get("link", ""),
        "query": it.get("query", ""),
        "classification": it["classification"],
        "published": it.get("published", ""),
    } for it in sorted_items[:5]]

    return {
        "ticker": ticker,
        "queries_run": len(queries),
        "total_items": total,
        "recent_items": recent_count,
        "bullish": bull,
        "bearish": bear,
        "neutral": neu,
        "intensity": intensity,
        "net_score": round(net, 3),
        "dynamic_coef": coef,
        "headlines": headlines,
        "evidence_tag": "Confirmed by Web Research",
        "scanned_at": _now_iso(),
    }


# =============================================================================
# Cache + Orchestration
# =============================================================================
def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("research cache load: %s", e)
        return {}


def _save_cache(data: dict) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.error("research cache save: %s", e)


def _is_stale() -> bool:
    c = _load_cache()
    ts = c.get("last_run")
    if not ts:
        return True
    try:
        last = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - last) > timedelta(hours=TTL_HOURS)
    except Exception:
        return True


def age_hours() -> float | None:
    c = _load_cache()
    ts = c.get("last_run")
    if not ts:
        return None
    try:
        last = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - last).total_seconds() / 3600
    except Exception:
        return None


def _update_milestones(scan: dict) -> None:
    """milestones.json'a 'Confirmed by Web Research' etiketi + intensity dus."""
    if not MILESTONES_FILE.exists():
        return
    with open(MILESTONES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    now = _now_iso()
    by_ticker = scan.get("by_ticker", {})

    for ticker, info in data.items():
        s = by_ticker.get(ticker)
        if not s:
            continue
        evidence = info.setdefault("evidence", [])
        # Eski 'RESEARCH_AGENT' kayitlarini temizle (yenisini ekle)
        evidence = [e for e in evidence if e.get("type") != "RESEARCH_AGENT"]
        evidence.append({
            "type": "RESEARCH_AGENT",
            "tag": "Confirmed by Web Research",
            "intensity": s.get("intensity", 0),
            "net_score": s.get("net_score", 0),
            "dynamic_coef": s.get("dynamic_coef", 1.0),
            "bullish": s.get("bullish", 0),
            "bearish": s.get("bearish", 0),
            "headlines": s.get("headlines", [])[:3],
            "timestamp": now,
        })
        info["evidence"] = evidence[-30:]
        info["last_research_agent"] = now

    with open(MILESTONES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_daily_research(force: bool = False,
                        tickers: list[str] | None = None,
                        progress_cb=None) -> dict:
    """
    Stale (>4 saat) veya force=True ise tum tickerlari tara.

    Returns: cache dict
    """
    if not force and not _is_stale():
        return _load_cache()

    tickers = tickers or list(RESEARCH_QUERIES.keys())
    result = {
        "last_run": _now_iso(),
        "ttl_hours": TTL_HOURS,
        "tickers_scanned": tickers,
        "by_ticker": {},
        "summary": {},
    }

    n = len(tickers)
    for i, t in enumerate(tickers):
        if progress_cb:
            progress_cb(f"{t}: haber yogunlugu...", (i + 1) / (n + 1))
        try:
            result["by_ticker"][t] = scan_ticker(t)
        except Exception as e:
            logger.error("scan_ticker %s: %s", t, e)
            result["by_ticker"][t] = {"error": str(e), "intensity": 0,
                                       "dynamic_coef": 1.0}

    # Aggregate summary (sektor genelinde "haber temperatursu")
    intensities = [d.get("intensity", 0) for d in result["by_ticker"].values()
                    if isinstance(d, dict)]
    net_scores = [d.get("net_score", 0) for d in result["by_ticker"].values()
                   if isinstance(d, dict)]
    if intensities:
        avg_int = sum(intensities) / len(intensities)
        avg_net = sum(net_scores) / len(net_scores)
        result["summary"] = {
            "avg_intensity": round(avg_int, 1),
            "avg_net_score": round(avg_net, 3),
            "max_intensity_ticker": max(result["by_ticker"].items(),
                                          key=lambda x: x[1].get("intensity",
                                                                   0))[0],
            "tickers_with_bull": sum(1 for d in result["by_ticker"].values()
                                       if isinstance(d, dict)
                                       and d.get("bullish", 0) > d.get("bearish", 0)),
            "tickers_with_bear": sum(1 for d in result["by_ticker"].values()
                                       if isinstance(d, dict)
                                       and d.get("bearish", 0) > d.get("bullish", 0)),
        }

    # milestones.json'a tag dus
    try:
        _update_milestones(result)
    except Exception as e:
        logger.error("milestones update (research): %s", e)

    _save_cache(result)
    if progress_cb:
        progress_cb("Tamam", 1.0)
    return result


# =============================================================================
# Accessor helpers (master_score, app.py kullanir)
# =============================================================================
def get_cache() -> dict:
    return _load_cache()


def is_stale() -> bool:
    return _is_stale()


def get_intensity(ticker: str) -> dict:
    """Bir hisse icin haber yogunlugu + net score."""
    cache = _load_cache()
    d = cache.get("by_ticker", {}).get(ticker, {})
    return {
        "intensity": d.get("intensity", 0),
        "net_score": d.get("net_score", 0.0),
        "dynamic_coef": d.get("dynamic_coef", 1.0),
        "bullish": d.get("bullish", 0),
        "bearish": d.get("bearish", 0),
        "headlines": d.get("headlines", []),
        "evidence_tag": "Confirmed by Web Research",
    }


def get_dynamic_master_coef(ticker: str) -> float:
    """
    Lopez de Prado MDA tarzi: Master Score'a uygulanacak feature-importance
    bazli dinamik carpan (0.5 .. 1.5). 1.0 = notr.
    """
    return float(_load_cache().get("by_ticker", {})
                  .get(ticker, {}).get("dynamic_coef", 1.0))


def get_dynamic_master_bonus(ticker: str) -> int:
    """
    Daha guvenli alternatif: dynamic_coef yerine additif +/- bonus (-10..+10)
    olarak ifade. coef=1.5 -> +10, coef=0.5 -> -10.
    """
    coef = get_dynamic_master_coef(ticker)
    bonus = round((coef - 1.0) * 20, 1)   # 0.5..1.5 -> -10..+10
    return int(max(-10, min(10, bonus)))
