"""
alpha_detector - sinyallerden ALPHA EVENT uretir.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config import settings
from src.analytics.zscore import compute_zscores
from src.common.signal_bus import Signal, get_signal_bus

LOG = logging.getLogger(__name__)

SOURCE_LABEL = {
    "sec_edgar": "SEC 8-K",
    "google_news": "Haber",
    "reddit_rss": "Reddit",
    "reddit": "Reddit",
    "polygon_options": "Opsiyon",
    "stocktwits": "StockTwits",
}

SOURCE_WEIGHT = {
    "sec_edgar": 2.5,
    "google_news": 1.5,
    "reddit_rss": 1.2,
    "reddit": 1.2,
    "polygon_options": 1.8,
}

RECENT_MIN = 20       # anlik uyari: sinyal / 8-K yasi (dk)
SEC_FILED_MAX_H = 72  # 8-K dosyalanma max yasi (saat)


@dataclass
class AlphaEvent:
    ticker: str
    composite: float
    severity: str  # KRITIK | YUKSEK | ORTA
    triggers: list[dict] = field(default_factory=list)
    headline: str = ""

    def dedupe_key(self) -> str:
        parts = sorted(t["source"] for t in self.triggers)
        return f"{self.ticker}:{','.join(parts)}"


class CooldownStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if self.path.is_file():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def _save(self) -> None:
        try:
            self.path.write_text(json.dumps(self._data), encoding="utf-8")
        except Exception as exc:
            LOG.warning("cooldown save: %s", exc)

    def allowed(self, key: str, cooldown_min: int) -> bool:
        last = self._data.get(key, 0)
        return (time.time() - last) >= cooldown_min * 60

    def mark(self, key: str) -> None:
        self._data[key] = time.time()
        self._save()


def _signal_age_minutes(s: Signal) -> float:
    # SEC icin dosyalanma tarihi daha dogru (toplu ingest spike onlenir)
    if s.source == "sec_edgar":
        filed = (s.metadata or {}).get("filed_at")
        if filed:
            try:
                fts = datetime.fromisoformat(filed.replace("Z", "+00:00"))
                if fts.tzinfo is None:
                    fts = fts.replace(tzinfo=timezone.utc)
                return (datetime.now(timezone.utc) - fts).total_seconds() / 60.0
            except Exception:
                pass
    ts = s.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 60.0


def _absolute_trigger(source: str, cur: float, meta: dict) -> Optional[str]:
    if source == "sec_edgar" and cur >= 1:
        filed = meta.get("filed_at")
        if filed:
            try:
                fts = datetime.fromisoformat(filed.replace("Z", "+00:00"))
                if fts.tzinfo is None:
                    fts = fts.replace(tzinfo=timezone.utc)
                age_h = (datetime.now(timezone.utc) - fts).total_seconds() / 3600
                if age_h > SEC_FILED_MAX_H:
                    return None
            except Exception:
                pass
        title = (meta.get("title") or "Material event 8-K")[:100]
        return title
    if source == "google_news" and cur >= 2:
        return (meta.get("latest_title") or f"{int(cur)} haber")[:100]
    if source in ("reddit_rss", "reddit") and cur >= 3:
        return f"{int(cur)} mention (1s)"
    if source == "polygon_options" and cur >= 2.5:
        return f"Call/Put oran {cur:.1f}x"
    return None


async def detect_alpha_events() -> list[AlphaEvent]:
    bus = get_signal_bus()
    signals = await bus.recent(lookback_h=72)
    zmap = compute_zscores(signals, current_window_h=1.0, baseline_window_h=72.0)

    # Son dakikalardaki taze sinyaller (anlik kurallar)
    fresh = [s for s in signals if _signal_age_minutes(s) <= RECENT_MIN]

    events: list[AlphaEvent] = []
    tickers = set(zmap.keys()) | {s.ticker.upper() for s in fresh}

    for ticker in tickers:
        triggers: list[dict] = []
        composite = 0.0

        # Z-score tabanli
        for source, info in zmap.get(ticker, {}).items():
            z = info["z"]
            w = SOURCE_WEIGHT.get(source, 1.0)
            if z >= settings.Z_TRIGGER:
                detail = _absolute_trigger(source, info["current"], info.get("metadata") or {})
                if not detail:
                    detail = f"z={z} deger={info['current']}"
                triggers.append({
                    "source": source,
                    "label": SOURCE_LABEL.get(source, source),
                    "z": z,
                    "value": info["current"],
                    "detail": detail,
                    "url": info.get("url"),
                })
                composite += z * w

        # Mutlak / taze sinyal kurallari
        for s in fresh:
            if s.ticker.upper() != ticker:
                continue
            detail = _absolute_trigger(s.source, s.value, s.metadata or {})
            if not detail:
                continue
            if any(t["source"] == s.source for t in triggers):
                continue
            triggers.append({
                "source": s.source,
                "label": SOURCE_LABEL.get(s.source, s.source),
                "z": 0.0,
                "value": s.value,
                "detail": detail,
                "url": s.url,
                "fresh": True,
            })
            composite += SOURCE_WEIGHT.get(s.source, 1.0) * 2.0

        if not triggers:
            continue

        n_sources = len({t["source"] for t in triggers})
        max_z = max(t.get("z", 0) for t in triggers)

        # Karar
        is_critical = (
            any(t["source"] == "sec_edgar" for t in triggers)
            or composite >= settings.COMPOSITE_TRIGGER + 2
            or max_z >= 4.5
        )
        is_high = (
            composite >= settings.COMPOSITE_TRIGGER
            or n_sources >= settings.MIN_SIGNALS_FOR_ALPHA
            or max_z >= settings.Z_TRIGGER
        )

        if not is_high:
            continue

        severity = "KRITIK" if is_critical else "YUKSEK"
        headline = triggers[0]["detail"]
        events.append(AlphaEvent(
            ticker=ticker,
            composite=round(composite, 1),
            severity=severity,
            triggers=triggers,
            headline=headline,
        ))

    events.sort(key=lambda e: -e.composite)
    return events


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
