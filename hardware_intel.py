"""
hardware_intel.py - Hardware Intelligence Agent (HIA).

24 saatte bir calisan otomatik ajan. Her saat baslangicta cache kontrol eder,
eger >24 saat eski ise tum modulleri yeniden tarar:

  - patent_watch.scan_patents()    (her hisse)
  - geopolitics.assess_ticker()    (her hisse)
  - semi_cycle.detect_cycle_phase()
  - 'Yield & Fab Intelligence' (Google News + filtre)

Sonuclar:
  - data/research_cache.json   (24h cache)
  - milestones.json   (Confirmed by Web Research etiketi)

Kullanım:
  from hardware_intel import HardwareIntelAgent
  agent = HardwareIntelAgent()
  agent.run_if_stale()   # 24h kontrolle
  data = agent.get_cache()
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import feedparser

from config import ALL_WATCHLIST_DEFAULTS, TICKERS

logger = logging.getLogger(__name__)


DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CACHE_FILE = DATA_DIR / "research_cache.json"
MILESTONES_FILE = Path(__file__).parent / "milestones.json"

DEFAULT_TTL_HOURS = 24


# --- Yield & Fab Intelligence queries ---------------------------------------
YIELD_QUERIES = {
    "WOLF": [
        "Mohawk Valley Fab utilization rate",
        "Wolfspeed 200mm SiC wafer yield 2026",
        "SiC MOSFET production ramp",
    ],
    "ASML": [
        "ASML High-NA EUV shipping updates",
        "ASML 2nm logic delivery",
        "High-NA installation TSMC Intel",
    ],
    "INTC": [
        "Intel 18A yield ramp 2026",
        "Intel Foundry IFS customer wins",
    ],
    "TSM": [
        "TSMC 2nm yield rate",
        "TSMC Arizona fab capacity",
    ],
    "0981.HK": [
        "SMIC 7nm yield 2026",
        "SMIC DUV multi-patterning capacity",
    ],
    "IONQ": [
        "IONQ AQ 64 milestone progress",
        "Forte Enterprise quantum delivery",
    ],
    "ATOM": [
        "Atomera MST licensing deal 2026",
        "MST JDA Foundry customer",
    ],
}


YIELD_PATTERN = re.compile(
    r"(?P<pct>\d{1,3})\s*%\s*(yield|utiliz|ramp)|"
    r"(yield|utiliz|ramp)\s*(of)?\s*(?P<pct2>\d{1,3})\s*%",
    re.IGNORECASE,
)


def _parse_yield_pct(text: str) -> int | None:
    m = YIELD_PATTERN.search(text or "")
    if not m:
        return None
    pct = m.group("pct") or m.group("pct2")
    try:
        v = int(pct)
        if 5 <= v <= 100:
            return v
    except (TypeError, ValueError):
        pass
    return None


def _fetch_news(query: str, limit: int = 5) -> list[dict]:
    url = (f"https://news.google.com/rss/search?"
           f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en")
    items = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:limit]:
            items.append({
                "title": e.get("title", ""),
                "summary": re.sub(r"<[^>]+>", "", e.get("summary", ""))[:240],
                "published": e.get("published", ""),
                "link": e.get("link", ""),
            })
    except Exception as ex:
        logger.debug("fetch_news %s hata: %s", query, ex)
    return items


def scan_yield_intelligence(ticker: str) -> dict:
    """Yield & Fab Intelligence - sayisal yield/utilization yakalama."""
    queries = YIELD_QUERIES.get(ticker, [])
    extracted = []
    raw_news = []
    for q in queries:
        for item in _fetch_news(q, limit=4):
            raw_news.append({**item, "query": q})
            text = item["title"] + " " + item["summary"]
            pct = _parse_yield_pct(text)
            if pct is not None:
                extracted.append({
                    "yield_pct": pct,
                    "query": q,
                    "title": item["title"][:160],
                    "link": item["link"],
                    "published": item["published"],
                })

    # En guncel yield rakami (varsa ortalama)
    if extracted:
        avg_yield = sum(x["yield_pct"] for x in extracted) / len(extracted)
        # Production Health: %50<- = sorunlu, %50-75 normal, %75+ saglikli
        if avg_yield >= 80:
            health = "🟢 ELITE PRODUCTION (>%80 yield)"
            score = 90
        elif avg_yield >= 65:
            health = "✅ SAGLIKLI URETIM"
            score = 70
        elif avg_yield >= 50:
            health = "📡 RAMPALAMA DEVAM"
            score = 50
        else:
            health = "⚠️ DUSUK YIELD - URETIM RISKI"
            score = 25
    else:
        avg_yield = None
        health = "❓ Yield verisi yok"
        score = 0

    return {
        "ticker": ticker,
        "yield_data_points": extracted,
        "avg_yield_pct": avg_yield,
        "production_health": health,
        "production_score": score,
        "raw_news_count": len(raw_news),
        "raw_news_sample": raw_news[:5],
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
class HardwareIntelAgent:
    def __init__(self, ttl_hours: int = DEFAULT_TTL_HOURS):
        self.ttl_hours = ttl_hours
        self.cache_file = CACHE_FILE

    # ---- Cache I/O -------------------------------------------------
    def _load_cache(self) -> dict:
        if not self.cache_file.exists():
            return {}
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("cache load: %s", e)
            return {}

    def _save_cache(self, data: dict) -> None:
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error("cache save: %s", e)

    def is_stale(self) -> bool:
        c = self._load_cache()
        ts = c.get("last_run")
        if not ts:
            return True
        try:
            last = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - last
            return age > timedelta(hours=self.ttl_hours)
        except Exception:
            return True

    def get_cache(self) -> dict:
        return self._load_cache()

    def age_hours(self) -> float | None:
        c = self._load_cache()
        ts = c.get("last_run")
        if not ts:
            return None
        try:
            last = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - last).total_seconds() / 3600
        except Exception:
            return None

    # ---- Run full scan ---------------------------------------------
    def run_full_scan(self, tickers: list[str] | None = None,
                       progress_cb=None) -> dict:
        """Tum modulleri calistir, cache'e yaz, milestones.json'a tag dus."""
        from geopolitics import assess_ticker
        from patent_watch import scan_patents
        from semi_cycle import detect_cycle_phase

        tickers = tickers or list(set(TICKERS + ALL_WATCHLIST_DEFAULTS))
        result = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "tickers_scanned": tickers,
            "patents": {},
            "geopolitics": {},
            "yield_intel": {},
            "semi_cycle": {},
        }

        # 1) Semi cycle (global, bir kere)
        try:
            if progress_cb: progress_cb("Yari iletken dongusu...", 0.05)
            result["semi_cycle"] = detect_cycle_phase()
        except Exception as e:
            logger.error("semi_cycle: %s", e)

        n = len(tickers)
        for i, t in enumerate(tickers):
            base = 0.1 + (i / n) * 0.9
            if progress_cb:
                progress_cb(f"{t}: patent + geo + yield...", base)
            # 2) Patent
            try:
                result["patents"][t] = scan_patents(t)
            except Exception as e:
                logger.error("patent %s: %s", t, e)
                result["patents"][t] = {"error": str(e)}
            # 3) Geopolitics
            try:
                # BIS Federal Register sadece bir kere yeterli (yavas)
                result["geopolitics"][t] = assess_ticker(t, include_bis=(i == 0))
            except Exception as e:
                logger.error("geo %s: %s", t, e)
                result["geopolitics"][t] = {"error": str(e)}
            # 4) Yield
            try:
                result["yield_intel"][t] = scan_yield_intelligence(t)
            except Exception as e:
                logger.error("yield %s: %s", t, e)
                result["yield_intel"][t] = {"error": str(e)}

        # 5) milestones.json update
        try:
            self._update_milestones(result)
        except Exception as e:
            logger.error("milestones update: %s", e)

        self._save_cache(result)
        if progress_cb: progress_cb("Tamam", 1.0)
        return result

    def run_if_stale(self, progress_cb=None) -> dict:
        if self.is_stale():
            logger.info("Cache stale or missing - running full scan...")
            return self.run_full_scan(progress_cb=progress_cb)
        return self._load_cache()

    # ---- milestones.json updater -----------------------------------
    def _update_milestones(self, scan: dict) -> None:
        """
        Web arastirmasiyla onaylanan milestone'lari isaretle.
        Patent / yield / cycle bulgularini 'evidence' olarak ekle.
        """
        if not MILESTONES_FILE.exists():
            logger.debug("milestones.json yok, atlandi")
            return
        with open(MILESTONES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        patents = scan.get("patents", {})
        yield_intel = scan.get("yield_intel", {})
        now_iso = datetime.now(timezone.utc).isoformat()

        for ticker, info in data.items():
            evidence = info.setdefault("evidence", [])
            # Patent kanitlari
            p = patents.get(ticker, {})
            if p.get("strategic_hits", 0) >= 1:
                evidence.append({
                    "type": "PATENT",
                    "tag": "Confirmed by Web Research",
                    "patent_bonus": p.get("patent_bonus", 0),
                    "count": p["strategic_hits"],
                    "label": p.get("label", ""),
                    "timestamp": now_iso,
                    "items": [
                        {"title": x.get("title", "")[:140],
                          "link": x.get("link", ""),
                          "source": x.get("source", "")}
                        for x in p.get("recent_items", [])[:3]
                    ],
                })

            # Yield kanitlari
            y = yield_intel.get(ticker, {})
            if y.get("avg_yield_pct") is not None:
                evidence.append({
                    "type": "YIELD",
                    "tag": "Confirmed by Web Research",
                    "yield_pct": y["avg_yield_pct"],
                    "health": y.get("production_health", ""),
                    "production_score": y.get("production_score", 0),
                    "timestamp": now_iso,
                    "data_points": y.get("yield_data_points", [])[:3],
                })

            # Cycle phase global ama her sirkete eklenir
            cycle = scan.get("semi_cycle", {})
            if cycle:
                evidence.append({
                    "type": "CYCLE_PHASE",
                    "tag": "Confirmed by Web Research",
                    "phase": cycle.get("phase", ""),
                    "cycle_score": cycle.get("cycle_score", 0),
                    "timestamp": now_iso,
                })

            # Sadece son 30 evidence sakla (sismeyi onle)
            info["evidence"] = evidence[-30:]
            info["last_research"] = now_iso

        with open(MILESTONES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================================
# Convenience accessor functions
# ============================================================================
_agent = HardwareIntelAgent()


def get_intel() -> dict:
    return _agent.get_cache()


def cache_age_hours() -> float | None:
    return _agent.age_hours()


def is_stale() -> bool:
    return _agent.is_stale()


def run_scan(force: bool = False, progress_cb=None) -> dict:
    if force or _agent.is_stale():
        return _agent.run_full_scan(progress_cb=progress_cb)
    return _agent.get_cache()


def get_patent_bonus(ticker: str) -> int:
    """Master Score icin patent bonusu (0..5)."""
    cache = _agent.get_cache()
    p = cache.get("patents", {}).get(ticker, {})
    return int(p.get("patent_bonus", 0))


def get_production_score(ticker: str) -> dict:
    """Production Health (moat_analysis'e enjekte)."""
    cache = _agent.get_cache()
    y = cache.get("yield_intel", {}).get(ticker, {})
    return {
        "avg_yield_pct": y.get("avg_yield_pct"),
        "production_health": y.get("production_health", "❓ Henuz taranmadi"),
        "production_score": y.get("production_score", 0),
    }


def get_geo_risk(ticker: str) -> dict:
    """Supply Chain Risk - kritik alarm kontrolu."""
    cache = _agent.get_cache()
    g = cache.get("geopolitics", {}).get(ticker, {})
    return {
        "risk_level": g.get("risk_level", "❓ Taranmadi"),
        "risk_score": g.get("risk_score", 0),
        "critical_alert": g.get("critical_alert", False),
        "export_weight": g.get("export_weight", 0),
        "negative_items": g.get("negative_items", []),
    }


def get_cycle_modifier() -> int:
    """Semi cycle modifier (Master Score'a) -3..+3."""
    cache = _agent.get_cache()
    return int(cache.get("semi_cycle", {}).get("modifier", 0))


def get_macro_bonus() -> int:
    """
    Makro Bonus: Expansion fazinda +10 (kullanici talebi V7).
    Recovery=+5, Trough=0, Peak=-5, Downturn=-10.
    """
    cache = _agent.get_cache()
    return int(cache.get("semi_cycle", {}).get("macro_bonus", 0))
