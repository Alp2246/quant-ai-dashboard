"""
StockTwitsScanner - Reddit yerine (API key YOK, onay YOK).

Kaynaklar:
    1) /trending/symbols/equities.json  -> su an populer hisseler
    2) /streams/symbol/{TICKER}.json    -> son mesajlar (mention velocity)

value = son 1 saatteki mesaj sayisi (trending'de ise +bonus metadata)

Rate limit: nazik kullan (~1 req/s). Tick basina max 8 ticker stream taranir
(rotasyon: her tick farkli offset).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from config import settings
from src.common.http_client import get_http_client
from src.ingestion.base import BaseScanner

LOG = logging.getLogger(__name__)
API = "https://api.stocktwits.com/api/2"
LOOKBACK_SEC = 3600
MAX_STREAMS_PER_TICK = 8


class StockTwitsScanner(BaseScanner):
    name = "stocktwits"

    def __init__(self) -> None:
        super().__init__()
        self.client = get_http_client()
        self.client.set_rate_limit("api.stocktwits.com", calls=10, per_seconds=1.0)
        self._ticker_set = {t.upper() for t in settings.TICKERS}
        self._rotate_offset = 0

    async def _get_json(self, path: str) -> Any:
        url = f"{API}{path}"
        return await self.client.get_json(
            url,
            headers={"User-Agent": "QuantAI-Alpha/1.0"},
        )

    async def _fetch_trending(self) -> set[str]:
        """Bizim evrendeki trending ticker'lar."""
        found: set[str] = set()
        try:
            data = await self._get_json("/trending/symbols/equities.json")
            for sym in (data.get("symbols") or []):
                t = (sym.get("symbol") or "").upper()
                if t in self._ticker_set:
                    found.add(t)
        except Exception as exc:
            LOG.warning("stocktwits trending err: %s", exc)
        return found

    async def _count_recent_messages(self, ticker: str) -> tuple[int, float]:
        """Son 1 saatteki mesaj sayisi + bullish oran (0..1)."""
        cutoff = time.time() - LOOKBACK_SEC
        try:
            data = await self._get_json(f"/streams/symbol/{ticker}.json?limit=30")
        except Exception as exc:
            LOG.debug("stocktwits stream [%s]: %s", ticker, exc)
            return 0, 0.0

        messages = data.get("messages") or []
        count = 0
        bull = 0
        for m in messages:
            created = m.get("created_at")
            if not created:
                continue
            try:
                # ISO: 2024-06-01T12:00:00Z
                ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
            except Exception:
                continue
            if ts < cutoff:
                continue
            count += 1
            entities = m.get("entities") or {}
            sentiment = entities.get("sentiment") or {}
            basic = (sentiment.get("basic") or "").lower()
            if basic == "bullish":
                bull += 1
        bull_ratio = bull / count if count > 0 else 0.0
        return count, bull_ratio

    async def poll(self, ctx) -> None:
        self._reset_run()
        trending = await self._fetch_trending()
        tickers = list(settings.TICKERS)
        n = len(tickers)
        if n == 0:
            return

        # Rotasyon: her tick farkli 8 ticker
        start = self._rotate_offset % n
        batch = []
        for i in range(min(MAX_STREAMS_PER_TICK, n)):
            batch.append(tickers[(start + i) % n])
        self._rotate_offset = (start + MAX_STREAMS_PER_TICK) % n

        # Trending olanlari once tara
        scan_order = list(dict.fromkeys(list(trending) + batch))

        emitted = 0
        for ticker in scan_order:
            count, bull_ratio = await self._count_recent_messages(ticker)
            is_trending = ticker in trending
            # Sinyal: mention sayisi; trending ise min 1 yeter
            if count <= 0 and not is_trending:
                continue
            value = float(count) + (5.0 if is_trending else 0.0)
            await self._emit(
                ticker=ticker,
                value=value,
                metadata={
                    "mentions_1h": count,
                    "bullish_ratio": round(bull_ratio, 2),
                    "trending": is_trending,
                    "lookback_sec": LOOKBACK_SEC,
                },
                url=f"https://stocktwits.com/symbol/{ticker}",
                event_id=f"{ticker}-{int(time.time()) // LOOKBACK_SEC}",
            )
            emitted += 1

        LOG.info("[stocktwits] trending=%d scanned=%d emitted=%d",
                 len(trending), len(scan_order), emitted)


async def poll(ctx) -> None:
    await _get_singleton().poll(ctx)


_singleton: Optional[StockTwitsScanner] = None


def _get_singleton() -> StockTwitsScanner:
    global _singleton
    if _singleton is None:
        _singleton = StockTwitsScanner()
    return _singleton
