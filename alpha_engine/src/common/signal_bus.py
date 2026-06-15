"""
signal_bus - paylasilan sinyal saklayicisi.

Tasarim:
    * Append-only JSONL: data/state/signals.jsonl
    * Bellekte rolling buffer (son 24 saat)
    * Thread/async safe (asyncio.Lock)
    * Analytics modulu (Adim 3) bunu okuyup z-score uretir
    * Eski sinyaller otomatik prune (default 24h)

Kullanim:
    bus = get_signal_bus()
    await bus.emit(Signal(source="sec_edgar", ticker="AXTI", value=1.0, ...))
    recent = await bus.recent("AXTI", source="sec_edgar", lookback_h=24)
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

LOG = logging.getLogger(__name__)


@dataclass
class Signal:
    source: str                          # "sec_edgar" | "polygon_options" | "reddit"
    ticker: str
    value: float                          # ham metrik (filing count, mention count, OR ratio...)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)
    url: Optional[str] = None
    event_id: Optional[str] = None        # dedup icin (filing_id, post_id...)

    def to_json(self) -> str:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "Signal":
        d = json.loads(raw)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**d)


class SignalBus:
    def __init__(self, path: Path, max_age_h: int = 24):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_age = timedelta(hours=max_age_h)
        self._lock = asyncio.Lock()
        self._buffer: list[Signal] = []
        self._seen_ids: set[str] = set()
        self._loaded = False

    async def _load_from_disk(self) -> None:
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            cutoff = datetime.now(timezone.utc) - self.max_age
            if self.path.is_file():
                try:
                    for line in self.path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            s = Signal.from_json(line)
                        except Exception:
                            continue
                        if s.timestamp >= cutoff:
                            self._buffer.append(s)
                            if s.event_id:
                                self._seen_ids.add(f"{s.source}:{s.event_id}")
                except Exception as exc:
                    LOG.warning("signal_bus disk read failed: %s", exc)
            self._loaded = True
            LOG.info("SignalBus yuklendi: %d aktif sinyal", len(self._buffer))

    def contains_event(self, event_id: str, source: Optional[str] = None) -> bool:
        """
        event_id daha onceden bus'a girmis mi? (XML/HTTP indirmesi yapmadan
        once dedup kontrolu icin). source verilmezse hangi source olursa olsun
        eslesirse True doner.
        """
        if source:
            return f"{source}:{event_id}" in self._seen_ids
        for key in self._seen_ids:
            if key.endswith(f":{event_id}"):
                return True
        return False

    async def emit(self, signal: Signal) -> bool:
        """
        Tek sinyal ekle. event_id verildiyse dedup yapilir; daha once gormussek
        False doner.
        """
        await self._load_from_disk()
        async with self._lock:
            if signal.event_id:
                key = f"{signal.source}:{signal.event_id}"
                if key in self._seen_ids:
                    return False
                self._seen_ids.add(key)
            self._buffer.append(signal)
            try:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(signal.to_json() + "\n")
            except Exception as exc:
                LOG.error("signal_bus append failed: %s", exc)
        return True

    async def recent(
        self,
        ticker: Optional[str] = None,
        source: Optional[str] = None,
        lookback_h: float = 1.0,
    ) -> list[Signal]:
        await self._load_from_disk()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_h)
        async with self._lock:
            return [
                s for s in self._buffer
                if s.timestamp >= cutoff
                and (ticker is None or s.ticker == ticker)
                and (source is None or s.source == source)
            ]

    async def prune(self) -> int:
        """Eski sinyalleri bellek + diskten temizler. Silinen sayisi doner."""
        await self._load_from_disk()
        cutoff = datetime.now(timezone.utc) - self.max_age
        async with self._lock:
            before = len(self._buffer)
            self._buffer = [s for s in self._buffer if s.timestamp >= cutoff]
            removed = before - len(self._buffer)
            if removed > 0:
                try:
                    with self.path.open("w", encoding="utf-8") as f:
                        for s in self._buffer:
                            f.write(s.to_json() + "\n")
                except Exception as exc:
                    LOG.error("signal_bus prune rewrite failed: %s", exc)
                LOG.info("SignalBus prune: %d eski sinyal silindi", removed)
            return removed


_singleton: Optional[SignalBus] = None


def get_signal_bus(path: Optional[Path] = None) -> SignalBus:
    global _singleton
    if _singleton is None:
        from config import settings
        _singleton = SignalBus(
            path or (settings.STATE_DIR / "signals.jsonl"),
            max_age_h=24,
        )
    return _singleton
