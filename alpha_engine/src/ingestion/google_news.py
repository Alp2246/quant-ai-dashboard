"""
GoogleNewsScanner - Reddit/StockTwits yerine (API key YOK, onay YOK).

Google News RSS:
    https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en

value = son LOOKBACK_H saatteki haber sayisi.
Haber spike = katalist yaklasiyor (AXTI, export ban vb.)

Cloudflare/403 sorunu yok; stdlib XML parser.
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import quote_plus

from config import settings
from src.common.http_client import get_http_client
from src.ingestion.base import BaseScanner

LOG = logging.getLogger(__name__)
LOOKBACK_H = 6
MAX_PER_TICK = 6
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

QUERY_MAP: dict[str, str] = {
    "AXTI": "AXT gallium arsenide export",
    "IONQ": "IonQ quantum",
    "RGTI": "Rigetti quantum",
    "WOLF": "Wolfspeed silicon carbide",
    "LAES": "SEALSQ post-quantum",
    "ATOM": "Atomera semiconductor",
    "NVTS": "Navitas GaN",
    "ASML": "ASML EUV lithography",
    "MU": "Micron HBM memory",
    "SMCI": "Super Micro AI server",
    "QBTS": "D-Wave quantum",
}


class GoogleNewsScanner(BaseScanner):
    name = "google_news"

    def __init__(self) -> None:
        super().__init__()
        self.client = get_http_client()
        self.client.set_rate_limit("news.google.com", calls=5, per_seconds=2.0)
        self._offset = 0

    def _query(self, ticker: str) -> str:
        return QUERY_MAP.get(ticker, f"{ticker} stock semiconductor")

    async def _fetch_rss(self, query: str) -> str:
        url = (
            "https://news.google.com/rss/search?"
            f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        )
        return await self.client.get_text(
            url,
            headers={"User-Agent": UA, "Accept": "application/rss+xml, */*"},
        )

    @staticmethod
    def _count_recent(xml_text: str, cutoff_ts: float) -> tuple[int, str]:
        """Returns (count, latest_title)."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return 0, ""
        count = 0
        latest_title = ""
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            pub = item.findtext("pubDate")
            if not pub:
                continue
            try:
                dt = parsedate_to_datetime(pub)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                ts = dt.timestamp()
            except Exception:
                continue
            if ts >= cutoff_ts:
                count += 1
                if not latest_title:
                    latest_title = title[:120]
        return count, latest_title

    async def poll(self, ctx) -> None:
        self._reset_run()
        tickers = list(settings.TICKERS)
        n = len(tickers)
        if n == 0:
            return

        start = self._offset % n
        batch = [tickers[(start + i) % n] for i in range(min(MAX_PER_TICK, n))]
        self._offset = (start + MAX_PER_TICK) % n

        cutoff_ts = time.time() - LOOKBACK_H * 3600
        emitted = 0

        for ticker in batch:
            query = self._query(ticker)
            try:
                xml_text = await self._fetch_rss(query)
            except Exception as exc:
                LOG.warning("google_news [%s]: %s", ticker, str(exc)[:150])
                continue
            count, latest = self._count_recent(xml_text, cutoff_ts)
            if count <= 0:
                continue
            await self._emit(
                ticker=ticker,
                value=float(count),
                metadata={
                    "query": query,
                    "articles_6h": count,
                    "latest_title": latest,
                    "lookback_h": LOOKBACK_H,
                },
                url=f"https://news.google.com/search?q={quote_plus(query)}",
                event_id=f"{ticker}-gn-{int(time.time()) // (LOOKBACK_H * 3600)}",
            )
            emitted += 1

        LOG.info("[google_news] scanned=%d emitted=%d", len(batch), emitted)


async def poll(ctx) -> None:
    await _get_singleton().poll(ctx)


_singleton: Optional[GoogleNewsScanner] = None


def _get_singleton() -> GoogleNewsScanner:
    global _singleton
    if _singleton is None:
        _singleton = GoogleNewsScanner()
    return _singleton
