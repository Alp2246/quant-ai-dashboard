"""
engine.py - CompositeAlphaEngine

Skor Stretching Felsefesi
=========================
NVDA gibi MEGA-cap hisseler 1 saatte 50 Reddit mention alabilirken,
AXTI gibi SMALL-cap hisseler icin 5 mention bile patlamadir.
Bu nedenle z-score'u TICKER bazinda DEGIL, KOHORT bazinda hesaplariz:

  cohort_z(t, s) = (t'nin son 1 saatlik s degeri - cohort baseline mean)
                   ---------------------------------------------------------
                                cohort baseline std

  cohort ∈ { MEGA, MID, SMALL }    ($200B / $10B threshold)

ALPHA EVENT kurali:
  Bir ticker icin AYNI KOHORTTA en az 2 farkli kaynak (Reddit + Opsiyon, ya da
  SEC + Reddit gibi) z > 3.0 esigini asarsa kompozit skorla event tetiklenir.

Persistans:
  - cohort_map.json     : {ticker: cohort} - yfinance ile 7 gunde bir refresh
  - cohort_baseline.json: {cohort:source: [(iso_ts, value), ...]} - 90g rolling
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import statistics
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config import settings
from src.common.signal_bus import Signal, get_signal_bus

LOG = logging.getLogger(__name__)


# ===========================================================================
#  Kohort tanimlari
# ===========================================================================
COHORT_NAMES = ("MEGA", "MID", "SMALL")

# Esikler (USD)
COHORT_THRESHOLDS = {
    "MEGA":  200_000_000_000,   # >= 200 milyar
    "MID":   10_000_000_000,    # 10 - 200 milyar
    "SMALL": 0,                  # < 10 milyar
}

# Bilinen ticker'lar icin hizli baslangic haritasi (yfinance beklemeden)
DEFAULT_COHORTS: dict[str, str] = {
    # MEGA-cap
    "NVDA": "MEGA", "MSFT": "MEGA", "AAPL": "MEGA", "GOOGL": "MEGA",
    "GOOG": "MEGA", "META": "MEGA", "AMZN": "MEGA", "TSLA": "MEGA",
    "AVGO": "MEGA", "ASML": "MEGA", "TSM": "MEGA", "ORCL": "MEGA",
    "PLTR": "MEGA",
    # MID-cap
    "AMD": "MID", "INTC": "MID", "QCOM": "MID", "MU": "MID",
    "MRVL": "MID", "ARM": "MID", "SMCI": "MID", "VRT": "MID",
    "CRDO": "MID", "ALAB": "MID",
    # SMALL-cap (ana hedef evrenimiz)
    "IONQ": "SMALL", "RGTI": "SMALL", "ATOM": "SMALL", "WOLF": "SMALL",
    "LAES": "SMALL", "NVTS": "SMALL", "QBTS": "SMALL", "POET": "SMALL",
    "ARQQ": "SMALL", "AXTI": "SMALL", "INDI": "SMALL", "QUBT": "SMALL",
    "AEHR": "SMALL", "LSCC": "SMALL", "AMBA": "SMALL",
}


# ===========================================================================
#  AlphaEvent (alpha_detector ile uyumlu - notifier degismez)
# ===========================================================================
@dataclass
class AlphaEvent:
    ticker: str
    composite: float
    severity: str                            # KRITIK | YUKSEK
    cohort: str = "UNKNOWN"                  # MEGA / MID / SMALL
    triggers: list[dict] = field(default_factory=list)
    headline: str = ""
    sentiment: Optional[dict] = None         # score_texts cikti dict

    def dedupe_key(self) -> str:
        parts = sorted(t["source"] for t in self.triggers)
        return f"{self.ticker}:{','.join(parts)}"


# ===========================================================================
#  Kaynak agirliklari + etiketler
# ===========================================================================
SOURCE_LABEL = {
    "sec_edgar": "SEC 8-K",
    "sec_form4": "Insider Buying",
    "google_news": "Haber",
    "reddit_rss": "Reddit",
    "reddit": "Reddit",
    "polygon_options": "Opsiyon",
    "stocktwits": "StockTwits",
}

SOURCE_WEIGHT = {
    "sec_edgar": 2.5,
    "sec_form4": 3.0,            # CEO/CFO PURCHASE en guclu sinyal
    "google_news": 1.5,
    "reddit_rss": 1.2,
    "reddit": 1.2,
    "polygon_options": 1.8,
}


# ===========================================================================
#  CooldownStore - ayni event'in tekrar tekrar yollanmasini engeller
# ===========================================================================
class CooldownStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, float] = {}
        if self.path.is_file():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def allowed(self, key: str, cooldown_min: int) -> bool:
        return (time.time() - self._data.get(key, 0)) >= cooldown_min * 60

    def mark(self, key: str) -> None:
        self._data[key] = time.time()
        try:
            self.path.write_text(json.dumps(self._data), encoding="utf-8")
        except Exception as exc:
            LOG.warning("cooldown save: %s", exc)


# ===========================================================================
#  Yardimcilar
# ===========================================================================
def _hour_bucket(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.replace(minute=0, second=0, microsecond=0)


def _classify_market_cap(cap_usd: float) -> str:
    if cap_usd is None or cap_usd <= 0:
        return "SMALL"
    if cap_usd >= COHORT_THRESHOLDS["MEGA"]:
        return "MEGA"
    if cap_usd >= COHORT_THRESHOLDS["MID"]:
        return "MID"
    return "SMALL"


# ===========================================================================
#  CompositeAlphaEngine
# ===========================================================================
class CompositeAlphaEngine:
    """
    Kohort tabanli z-score motoru. Tek instance (singleton); state diskte.

    Public API:
        await engine.ensure_cohorts(tickers)
        await engine.update_and_detect(window_h=1.0) -> list[AlphaEvent]
        engine.cohort_of(ticker) -> "MEGA"|"MID"|"SMALL"
        engine.snapshot() -> dict   (debug / dashboard icin)
    """

    BASELINE_DAYS = 90
    Z_TRIGGER = None              # settings'den dinamik
    MIN_SOURCES = None            # settings'den dinamik
    COHORT_REFRESH_DAYS = 7

    def __init__(self) -> None:
        self.state_dir: Path = settings.STATE_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cohort_path = self.state_dir / "cohort_map.json"
        self.baseline_path = self.state_dir / "cohort_baseline.json"

        # ticker -> cohort
        self.cohort_map: dict[str, str] = {}
        # ticker -> market_cap (USD) — debug
        self.market_caps: dict[str, float] = {}

        # (cohort, source) -> list[(hour_iso, value)] rolling 90g
        self.baseline: dict[str, list] = defaultdict(list)

        self._lock = asyncio.Lock()
        self._last_cohort_refresh = 0.0

        self._load()

    # ---- Persistans ------------------------------------------------------
    def _load(self) -> None:
        if self.cohort_path.is_file():
            try:
                data = json.loads(self.cohort_path.read_text(encoding="utf-8"))
                self.cohort_map = data.get("cohorts", {})
                self.market_caps = data.get("caps", {})
                self._last_cohort_refresh = data.get("updated", 0.0)
            except Exception as exc:
                LOG.warning("cohort_map yukleme: %s", exc)
        # Bilinen default'lari uygula (eksikleri tamamla)
        for t, c in DEFAULT_COHORTS.items():
            self.cohort_map.setdefault(t, c)

        if self.baseline_path.is_file():
            try:
                raw = json.loads(self.baseline_path.read_text(encoding="utf-8"))
                for k, v in raw.items():
                    self.baseline[k] = list(v)
            except Exception as exc:
                LOG.warning("baseline yukleme: %s", exc)
        LOG.info("CompositeAlphaEngine: %d cohort entry, %d baseline series",
                 len(self.cohort_map), len(self.baseline))

    def _save_cohorts(self) -> None:
        try:
            self.cohort_path.write_text(json.dumps({
                "cohorts": self.cohort_map,
                "caps": self.market_caps,
                "updated": time.time(),
            }, indent=2), encoding="utf-8")
        except Exception as exc:
            LOG.warning("cohort save: %s", exc)

    def _save_baseline(self) -> None:
        try:
            self.baseline_path.write_text(
                json.dumps({k: v for k, v in self.baseline.items()}),
                encoding="utf-8",
            )
        except Exception as exc:
            LOG.warning("baseline save: %s", exc)

    # ---- Kohort tespiti --------------------------------------------------
    def cohort_of(self, ticker: str) -> str:
        return self.cohort_map.get(ticker.upper(), "SMALL")

    async def ensure_cohorts(self, tickers: list[str]) -> None:
        """Eksik / eski ticker'lari yfinance ile siniflandirir (background)."""
        now = time.time()
        needs_refresh = (now - self._last_cohort_refresh) > self.COHORT_REFRESH_DAYS * 86400
        missing = [t for t in tickers if t.upper() not in self.cohort_map]
        if not missing and not needs_refresh:
            return

        to_fetch = missing if missing else tickers
        try:
            results = await asyncio.to_thread(_fetch_market_caps, to_fetch)
        except Exception as exc:
            LOG.warning("market cap fetch hata: %s", exc)
            return

        async with self._lock:
            for t, cap in results.items():
                if cap is None:
                    continue
                self.market_caps[t] = float(cap)
                self.cohort_map[t] = _classify_market_cap(cap)
            self._last_cohort_refresh = now
            self._save_cohorts()
        LOG.info("Kohort guncellendi: %d ticker tarandi", len(to_fetch))

    # ---- Baseline guncelleme --------------------------------------------
    async def _ingest_signals_to_baseline(self, signals: list[Signal]) -> None:
        """Bu tick'in sinyallerini hourly bucket'lara ekler."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.BASELINE_DAYS)
        # ticker bazinda saatlik gruplar
        groups: dict[tuple[str, str, datetime], float] = defaultdict(float)
        for s in signals:
            cohort = self.cohort_of(s.ticker)
            hb = _hour_bucket(s.timestamp)
            groups[(cohort, s.source, hb)] += float(s.value)

        async with self._lock:
            # 1) Dokunulan (cohort,source) serileri: ayni saat MAX al, prune et
            for (cohort, source, hb), val in groups.items():
                key = f"{cohort}|{source}"
                hb_iso = hb.isoformat()
                series = self.baseline.get(key, [])

                pruned: list[tuple[str, float]] = []
                hour_seen = False
                for iso, v in series:
                    if _parse_iso(iso) < cutoff:
                        continue
                    if iso == hb_iso:
                        pruned.append((iso, max(v, val)))
                        hour_seen = True
                    else:
                        pruned.append((iso, v))
                if not hour_seen:
                    pruned.append((hb_iso, val))
                pruned.sort()
                self.baseline[key] = pruned

            # 2) Dokunulmayan serilerin eski kayitlarini prune et
            for key in list(self.baseline.keys()):
                self.baseline[key] = [
                    (iso, v) for iso, v in self.baseline[key]
                    if _parse_iso(iso) >= cutoff
                ]

            self._save_baseline()

    # ---- Z-score (kohort bazinda) ---------------------------------------
    def _zscore(self, cohort: str, source: str,
                current_value: float) -> tuple[float, float, float, int]:
        """Returns (z, mean, std, n_samples)."""
        series = [v for _, v in self.baseline.get(f"{cohort}|{source}", [])]
        if len(series) < 5:
            # cold start: yetersiz veri
            if current_value <= 0:
                return 0.0, 0.0, 0.0, len(series)
            # zayif z proxy: 3 esigi gecsin diye mutlak deger > 2 baz alir
            proxy = 3.0 if current_value >= 2 else 1.5
            return proxy, 0.0, 0.0, len(series)
        mean = statistics.fmean(series)
        try:
            std = statistics.stdev(series)
        except statistics.StatisticsError:
            std = 0.0
        if std < 1e-6:
            return (3.5 if current_value > mean else 0.0), mean, std, len(series)
        z = (current_value - mean) / std
        return round(z, 2), round(mean, 2), round(std, 2), len(series)

    # --- Decay parametreleri ---
    # Yari-omur 6 saat: 6h sonra %50, 12h sonra %25, 24h sonra %6, 72h sonra %0.05
    # Bu sayede sabah 10:00 Reddit spike + ogleden sonra 14:00 SEC 8-K
    # ayni event olarak korrobore edilir (Reddit zayiflamis ama hala >0.5 katki).
    DECAY_HALF_LIFE_H = 6.0
    DECAY_MAX_AGE_H = 72.0

    def _aggregate_current(self, signals: list[Signal],
                            window_h: float = None) -> dict[str, dict[str, dict]]:
        """
        Exponential decay agreger:
            value_efektif = sum_i ( raw_value_i * exp(-lambda * age_h_i) )
            lambda = ln(2) / yari_omur

        window_h parametresi geri-uyumluluk icin var; decay'i overlay yapar
        ama yine tum 72 saati tarar.
        """
        now = datetime.now(timezone.utc)
        max_age = self.DECAY_MAX_AGE_H
        lam = math.log(2) / self.DECAY_HALF_LIFE_H

        agg: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(
            lambda: {
                "value": 0.0,            # decayed effective
                "raw_peak": 0.0,         # decay olmadan en buyuk tek event
                "peak_age_h": 0.0,       # en buyuk event'in yasi
                "n_events": 0,
                "metadata": {},
                "url": None,
            }
        ))
        latest_ts: dict[tuple[str, str], datetime] = {}

        for s in signals:
            ts = s.timestamp if s.timestamp.tzinfo else s.timestamp.replace(tzinfo=timezone.utc)
            age_h = (now - ts).total_seconds() / 3600.0
            if age_h < 0 or age_h > max_age:
                continue
            decay = math.exp(-lam * age_h)
            raw = float(s.value)
            contribution = raw * decay

            d = agg[s.ticker.upper()][s.source]
            d["value"] += contribution
            d["n_events"] += 1
            if raw > d["raw_peak"]:
                d["raw_peak"] = raw
                d["peak_age_h"] = round(age_h, 2)

            key = (s.ticker.upper(), s.source)
            if key not in latest_ts or ts > latest_ts[key]:
                latest_ts[key] = ts
                d["metadata"] = dict(s.metadata or {})
                d["url"] = s.url

        # Yuvarlama (mesaj formatlama icin)
        for ticker_d in agg.values():
            for src_d in ticker_d.values():
                src_d["value"] = round(src_d["value"], 2)
        return agg

    # ---- Public: ana cevrim ----------------------------------------------
    async def update_and_detect(self, *, window_h: float = 1.0
                                  ) -> list[AlphaEvent]:
        """
        1) Son 72 saatlik sinyalleri al
        2) Baseline'a entegre et (rolling 90g)
        3) Kohort bazli z-score hesapla
        4) Multi-source z>=Z_TRIGGER kuralini uygula -> AlphaEvent
        """
        self.Z_TRIGGER = float(settings.Z_TRIGGER)
        self.MIN_SOURCES = int(settings.MIN_SIGNALS_FOR_ALPHA or 2)
        # ALPHA kurali en az 2 farkli kaynak ister (default 2);
        # kullanici MIN_SIGNALS_FOR_ALPHA=3 yazsa bile 2'den asagi inmesin
        min_required = max(2, min(3, self.MIN_SOURCES))

        bus = get_signal_bus()
        # baseline icin gectigimiz 72 saat - daha uzun istemiyoruz cunku
        # SignalBus zaten 24 saatlik tutuyor; baseline.json gercek 90g.
        signals = await bus.recent(lookback_h=72)
        if not signals:
            return []

        # 1) baseline entegre
        await self._ingest_signals_to_baseline(signals)

        # 2) son window_h icindeki "current" agregeler
        current_agg = self._aggregate_current(signals, window_h=window_h)

        # 3+4) kohort z + event
        events: list[AlphaEvent] = []
        for ticker, by_source in current_agg.items():
            cohort = self.cohort_of(ticker)
            triggers: list[dict] = []
            composite = 0.0

            for source, info in by_source.items():
                val = info["value"]                 # decay-adjusted
                raw_peak = info.get("raw_peak", val)
                peak_age = info.get("peak_age_h", 0.0)
                if val <= 0:
                    continue
                # z-score: decay-adjusted deger vs cohort baseline (saatlik)
                z, mean, std, n = self._zscore(cohort, source, val)
                if z < self.Z_TRIGGER:
                    continue
                detail = self._build_detail(source, raw_peak, info["metadata"])
                # Yas eklemesi: kullanici "ne zaman olmus" gorebilsin
                if peak_age >= 1:
                    detail += f"  [{peak_age:.0f}s once]"
                triggers.append({
                    "source": source,
                    "label": SOURCE_LABEL.get(source, source),
                    "z": z,
                    "value": round(val, 2),          # decay-adjusted
                    "raw_peak": round(raw_peak, 2),
                    "peak_age_h": peak_age,
                    "cohort_mean": mean,
                    "cohort_std": std,
                    "n_baseline": n,
                    "n_events": info.get("n_events", 1),
                    "detail": detail,
                    "url": info.get("url"),
                    "metadata": dict(info.get("metadata") or {}),
                })
                composite += z * SOURCE_WEIGHT.get(source, 1.0)

            if not triggers:
                continue

            n_sources = len(triggers)
            max_z = max(t["z"] for t in triggers)
            has_sec = any(t["source"] == "sec_edgar" for t in triggers)
            has_insider_buy = any(
                t["source"] == "sec_form4" and (t.get("raw_peak", 0) or 0) >= 2.0
                for t in triggers
            )
            # KOMPOZIT KURAL:
            #   >=2 farkli kaynak z>=Z_TRIGGER -> EVENT (ana kural)
            #   VEYA SEC 8-K tek basina (regulator zorunlu material event)
            #   VEYA Insider Buy (CEO/CFO nakit alimi, value_score >= 2)
            #   VEYA tek kaynak ama z>=5.5 (ekstrem)
            qualifies = (
                n_sources >= min_required
                or has_sec
                or has_insider_buy
                or max_z >= 5.5
            )
            if not qualifies:
                continue

            # ---- Sentiment analizi: haber + reddit basliklarini topla ----
            from src.analytics.sentiment import score_texts, severity_boost
            sentiment_texts: list[str] = []
            for t in triggers:
                meta = t.get("metadata") or {}
                if t["source"] == "sec_edgar":
                    title = meta.get("title")
                    if title:
                        sentiment_texts.append(str(title))
                elif t["source"] == "google_news":
                    title = meta.get("latest_title")
                    if title:
                        sentiment_texts.append(str(title))
                elif t["source"] in ("reddit_rss", "reddit"):
                    # Reddit basliklari metadata'da yok (sadece sayim); pas
                    pass
            sentiment = score_texts(sentiment_texts) if sentiment_texts else None
            boost = severity_boost(sentiment["mean"], sentiment["n"]) if sentiment else 1.0
            composite_boosted = round(composite * boost, 1)

            severity = "KRITIK" if (
                has_sec
                or has_insider_buy
                or composite_boosted >= settings.COMPOSITE_TRIGGER + 2
                or max_z >= 4.5
                or n_sources >= 3
                or (sentiment and sentiment["mean"] <= -2.5 and sentiment["n"] >= 3)
            ) else "YUKSEK"

            sorted_triggers = sorted(triggers, key=lambda t: -t["z"])
            events.append(AlphaEvent(
                ticker=ticker,
                composite=composite_boosted,
                severity=severity,
                cohort=cohort,
                triggers=sorted_triggers,
                headline=sorted_triggers[0]["detail"],
                sentiment=sentiment,
            ))

        events.sort(key=lambda e: -e.composite)
        return events

    # ---- Detay metin uretici --------------------------------------------
    @staticmethod
    def _build_detail(source: str, value: float, meta: dict) -> str:
        if source == "sec_edgar":
            return (meta.get("title") or "8-K material event")[:120]
        if source == "google_news":
            return (meta.get("latest_title") or f"{int(value)} haber (6s)")[:120]
        if source in ("reddit_rss", "reddit"):
            return f"{int(value)} mention (1s)"
        if source == "polygon_options":
            return f"Call/Put oran {value:.2f}x"
        if source == "stocktwits":
            return f"{int(value)} mesaj (1s)"
        return f"deger {value:.2f}"

    # ---- Debug / dashboard ----------------------------------------------
    def snapshot(self) -> dict:
        cohort_counts = defaultdict(int)
        for c in self.cohort_map.values():
            cohort_counts[c] += 1
        baseline_summary = {}
        for key, ser in self.baseline.items():
            cohort, source = key.split("|", 1)
            baseline_summary[key] = {
                "n_points": len(ser),
                "last_value": ser[-1][1] if ser else 0,
            }
        return {
            "cohort_counts": dict(cohort_counts),
            "n_tickers": len(self.cohort_map),
            "baseline": baseline_summary,
            "z_trigger": settings.Z_TRIGGER,
            "min_sources": settings.MIN_SIGNALS_FOR_ALPHA,
        }


def _parse_iso(iso: str) -> datetime:
    try:
        ts = datetime.fromisoformat(iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except Exception:
        return datetime.now(timezone.utc) - timedelta(days=365)


# ---------------------------------------------------------------------------
#  yfinance market cap fetcher (sync - asyncio.to_thread ile cagrilir)
# ---------------------------------------------------------------------------
def _fetch_market_caps(tickers: list[str]) -> dict[str, Optional[float]]:
    out: dict[str, Optional[float]] = {}
    try:
        import yfinance as yf  # noqa: PLC0415
    except ImportError:
        LOG.warning("yfinance yok; default cohort'lar kullanilacak")
        return {t: None for t in tickers}
    for t in tickers:
        try:
            info = yf.Ticker(t).info or {}
            cap = info.get("marketCap")
            out[t.upper()] = float(cap) if cap else None
        except Exception as exc:
            LOG.debug("yfinance %s: %s", t, exc)
            out[t.upper()] = None
    return out


# ===========================================================================
#  Singleton
# ===========================================================================
_engine_singleton: Optional[CompositeAlphaEngine] = None


def get_engine() -> CompositeAlphaEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = CompositeAlphaEngine()
    return _engine_singleton


# ===========================================================================
#  Public helpers - alpha_notify burayi cagirir
# ===========================================================================
async def detect_alpha_events() -> list[AlphaEvent]:
    engine = get_engine()
    await engine.ensure_cohorts(settings.TICKERS)
    return await engine.update_and_detect(window_h=1.0)


async def filter_with_cooldown(events: list[AlphaEvent]) -> list[AlphaEvent]:
    store = CooldownStore(settings.STATE_DIR / "alert_cooldown.json")
    out: list[AlphaEvent] = []
    for ev in events:
        key = ev.dedupe_key()
        mins = settings.ALERT_COOLDOWN_MIN
        if ev.severity == "KRITIK":
            mins = max(30, mins // 2)
        if store.allowed(key, mins):
            out.append(ev)
            store.mark(key)
    return out
