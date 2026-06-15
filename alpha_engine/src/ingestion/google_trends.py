"""
GoogleTrendsScanner - arama hacmi spike (Reddit alternatifi, API key YOK).

pytrends kullanir (pip install pytrends). Yoksa gracefully skip.

Her tick'te 3 ticker taranir (rotasyon). value = son 1 saatlik
interest relative to baseline (0-100 Google scale).

AXTI tipi olaylarda "gallium export" gibi anahtar kelimeler icin
ileride TICKER_KEYWORDS map'i genisletilebilir.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from config import settings
from src.ingestion.base import BaseScanner

LOG = logging.getLogger(__name__)

# Ticker -> Google arama terimi (sirket adi daha iyi sinyal verir)
SEARCH_TERMS: dict[str, str] = {
    "AXTI": "AXT Inc stock",
    "IONQ": "IonQ stock",
    "RGTI": "Rigetti stock",
    "WOLF": "Wolfspeed stock",
    "NVTS": "Navitas stock",
    "LAES": "SEALSQ stock",
    "ATOM": "Atomera stock",
    "ASML": "ASML stock",
    "MU": "Micron stock",
    "SMCI": "Super Micro stock",
    "QBTS": "D-Wave stock",
}

TICKS_PER_RUN = 3


def _interest_sync(keyword: str) -> float:
    """Blocking pytrends call - executor'da calisir."""
    try:
        from pytrends.request import TrendReq  # noqa: PLC0415
    except ImportError:
        return -1.0

    pytrends = TrendReq(hl="en-US", tz=0, retries=2, backoff_factor=0.5)
    pytrends.build_payload([keyword], timeframe="now 1-H", geo="US")
    df = pytrends.interest_over_time()
    if df is None or df.empty:
        return 0.0
    col = keyword if keyword in df.columns else df.columns[0]
    series = df[col]
    if len(series) == 0:
        return 0.0
    # Son deger = guncel ilgi; spike icin son / ortalama
    last = float(series.iloc[-1])
    avg = float(series.mean()) or 1.0
    return round(last / avg * 50, 1)  # normalize ~0-100+


class GoogleTrendsScanner(BaseScanner):
    name = "google_trends"

    def __init__(self) -> None:
        super().__init__()
        self._offset = 0
        self._pytrends_ok: Optional[bool] = None

    async def _check_pytrends(self) -> bool:
        if self._pytrends_ok is not None:
            return self._pytrends_ok
        try:
            await asyncio.to_thread(
                lambda: __import__("pytrends.request", fromlist=["TrendReq"])
            )
            self._pytrends_ok = True
        except ImportError:
            LOG.warning(
                "pytrends yuklu degil -> google_trends atlanir. "
                "Kur: pip install pytrends"
            )
            self._pytrends_ok = False
        return self._pytrends_ok

    async def poll(self, ctx) -> None:
        self._reset_run()
        if not await self._check_pytrends():
            return

        # Oncelik: SEARCH_TERMS'te tanimli olanlar
        priority = [t for t in settings.TICKERS if t in SEARCH_TERMS]
        rest = [t for t in settings.TICKERS if t not in SEARCH_TERMS]
        ordered = priority + rest

        n = len(ordered)
        if n == 0:
            return
        start = self._offset % n
        batch = [ordered[(start + i) % n] for i in range(min(TICKS_PER_RUN, n))]
        self._offset = (start + TICKS_PER_RUN) % n

        emitted = 0
        for ticker in batch:
            keyword = SEARCH_TERMS.get(ticker, f"{ticker} stock")
            try:
                score = await asyncio.wait_for(
                    asyncio.to_thread(_interest_sync, keyword),
                    timeout=25,
                )
            except asyncio.TimeoutError:
                LOG.warning("google_trends timeout [%s]", ticker)
                continue
            except Exception as exc:
                LOG.warning("google_trends [%s]: %s", ticker, exc)
                continue
            if score < 0:
                return  # pytrends import failed mid-run
            if score <= 5:
                continue
            await self._emit(
                ticker=ticker,
                value=score,
                metadata={"keyword": keyword, "interest_ratio": score},
                url=f"https://trends.google.com/trends/explore?q={keyword.replace(' ', '%20')}",
                event_id=f"{ticker}-gt-{int(time.time()) // 3600}",
            )
            emitted += 1
            await asyncio.sleep(2)  # Google rate limit

        LOG.info("[google_trends] scanned=%d emitted=%d", len(batch), emitted)


async def poll(ctx) -> None:
    await _get_singleton().poll(ctx)


_singleton: Optional[GoogleTrendsScanner] = None


def _get_singleton() -> GoogleTrendsScanner:
    global _singleton
    if _singleton is None:
        _singleton = GoogleTrendsScanner()
    return _singleton
