"""
PolygonOptionsScanner - unusual options activity scanner.

Strateji:
    Bir ticker icin SU AN'in option zincirine bak, gunluk call ve put
    volume'larini topla, call/put oranini hesapla.

    Yuksek oran (>2.0) + ortalama uzeri volume = institutional bullish setup.
    Bu cogu zaman haberden ONCE olusur (akilli para front-running yapar).

Plan:
    GET /v3/snapshot/options/{ticker}
      -> her opsiyon icin day.volume, type ("call"/"put") doner.
    Topla, oran hesapla, signal yayinla.

Limits (free tier):
    5 calls/dakika. Bu yuzden tick basina sadece "high-priority" ticker'lara
    bakariz (default ilk 5). Ileride premium key alirsan TICKERS'in tamamina
    bakariz.

API:
    https://polygon.io/docs/options/get_v3_snapshot_options__underlyingasset_

ATAMA YAPILMAMISSA:
    POLYGON_API_KEY .env'de yoksa scanner DISABLED loglar, hata atmaz.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from config import settings
from src.common.http_client import get_http_client
from src.ingestion.base import BaseScanner

LOG = logging.getLogger(__name__)
HOST = "api.polygon.io"
BASE = "https://api.polygon.io"


class PolygonOptionsScanner(BaseScanner):
    name = "polygon_options"

    def __init__(self, *, max_tickers_per_tick: int = 5) -> None:
        super().__init__()
        self.api_key = settings.POLYGON_API_KEY
        self.max_per_tick = max_tickers_per_tick
        self.client = get_http_client()
        # Free tier: 5 req/min
        self.client.set_rate_limit(HOST, calls=5, per_seconds=60.0)

    async def _fetch_chain(self, ticker: str) -> Optional[dict[str, Any]]:
        if not self.api_key:
            return None
        # Tum chain'i tek seferde getir; cursor'la sayfa baglanir ama
        # tek sayfa (250 contract) cogu hisse icin yeterli.
        url = (f"{BASE}/v3/snapshot/options/{ticker}"
               f"?limit=250&apiKey={self.api_key}")
        try:
            data = await self.client.get_json(url)
            return data
        except Exception as exc:
            msg = str(exc)[:200]
            # 401/403 = key gecersiz; tickerlari surekli denemeyelim
            if "401" in msg or "403" in msg:
                LOG.error("Polygon API key reddedildi: %s", msg)
                self.api_key = None
            else:
                LOG.warning("polygon fetch err [%s]: %s", ticker, msg)
            return None

    @staticmethod
    def _aggregate(chain: dict[str, Any]) -> tuple[float, float, int]:
        """
        Returns: (call_vol, put_vol, n_contracts)
        """
        call_vol = 0.0
        put_vol = 0.0
        n = 0
        for c in (chain.get("results") or []):
            details = c.get("details") or {}
            day = c.get("day") or {}
            vol = float(day.get("volume") or 0)
            ctype = (details.get("contract_type") or "").lower()
            if vol <= 0:
                continue
            if ctype == "call":
                call_vol += vol
            elif ctype == "put":
                put_vol += vol
            n += 1
        return call_vol, put_vol, n

    async def poll(self, ctx) -> None:
        self._reset_run()
        if not self.api_key:
            LOG.debug("polygon_options: API key yok, atlandi")
            return

        # Sadece ilk N ticker (rate limit yuzunden)
        tickers = settings.TICKERS[:self.max_per_tick]
        emitted = 0

        for ticker in tickers:
            chain = await self._fetch_chain(ticker)
            if not chain or not chain.get("results"):
                continue
            call_vol, put_vol, n = self._aggregate(chain)
            if call_vol + put_vol < 10:  # cok zayif, gurultu
                continue
            ratio = call_vol / put_vol if put_vol > 0 else (call_vol if call_vol > 0 else 0.0)
            await self._emit(
                ticker=ticker,
                value=ratio,
                metadata={
                    "call_volume": call_vol,
                    "put_volume": put_vol,
                    "n_contracts": n,
                    "total_volume": call_vol + put_vol,
                },
                url=f"https://www.optionsprofitcalculator.com/calculator/long-call.html?ticker={ticker}",
            )
            emitted += 1

        LOG.info("[polygon_options] scanned=%d emitted=%d", len(tickers), emitted)


async def poll(ctx) -> None:
    scanner = _get_singleton()
    await scanner.poll(ctx)


_singleton: Optional[PolygonOptionsScanner] = None


def _get_singleton() -> PolygonOptionsScanner:
    global _singleton
    if _singleton is None:
        _singleton = PolygonOptionsScanner()
    return _singleton
