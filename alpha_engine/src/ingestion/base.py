"""
ingestion.base - tum scanner'larin paylastigi temel.

Her scanner sinifindan poll(ctx) yontemi orchestrator tarafindan tick basina
bir kez cagrilir. Hata izolasyonu orchestrator'da; burada sadece sinyal
yayinlama ve durum kayda alma var.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from src.common.signal_bus import Signal, get_signal_bus

LOG = logging.getLogger(__name__)


class BaseScanner(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self.bus = get_signal_bus()
        self._emitted_total = 0
        self._last_run_emitted = 0

    @abstractmethod
    async def poll(self, ctx) -> None:
        """orchestrator tarafindan cagirilir. ctx = TaskContext."""

    async def _emit(self, *, ticker: str, value: float, metadata: Optional[dict] = None,
                    url: Optional[str] = None, event_id: Optional[str] = None) -> bool:
        sig = Signal(
            source=self.name,
            ticker=ticker.upper(),
            value=float(value),
            metadata=metadata or {},
            url=url,
            event_id=event_id,
        )
        ok = await self.bus.emit(sig)
        if ok:
            self._emitted_total += 1
            self._last_run_emitted += 1
        return ok

    def _reset_run(self) -> None:
        self._last_run_emitted = 0
