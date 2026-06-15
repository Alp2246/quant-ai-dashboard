"""
RedditRSSScanner - Reddit API / onay OLMADAN public RSS.

Kendi hesabinla tarayicida bakmak ile ayni icerik (public subreddit'ler):
    https://www.reddit.com/r/wallstreetbets/new/.rss
    https://www.reddit.com/r/stocks/new/.rss

Giris yapmaya gerek yok; sifre/API key yok.
Ozel mesajlar veya kayitli oldugun private sub'lar gelmez - sadece public.

Not: Resmi Reddit API (PRAW) daha zengin; onay alirsan reddit.py otomatik acilir.
"""
from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from config import settings
from src.common.http_client import get_http_client
from src.common.ticker_validator import get_validator
from src.ingestion.base import BaseScanner

LOG = logging.getLogger(__name__)

SUBREDDITS = ("wallstreetbets", "stocks", "stockmarket", "investing", "options")
LOOKBACK_SEC = 3600
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class RedditRSSScanner(BaseScanner):
    name = "reddit_rss"

    def __init__(self) -> None:
        super().__init__()
        self.client = get_http_client()
        self.client.set_rate_limit("www.reddit.com", calls=3, per_seconds=2.0)
        # Sadece izlenen ticker evrenine sinyal at (gurultu azaltir).
        # Master list (SEC) BLOCKLIST elemesi icin ticker_validator'in icinde.
        self._validator = get_validator(universe=set(settings.TICKERS))

    def _extract(self, text: str) -> set[str]:
        return self._validator.extract_tickers(text)

    async def _fetch_sub(self, sub: str, cutoff_ts: float) -> dict[str, int]:
        url = f"https://www.reddit.com/r/{sub}/new/.rss?limit=100"
        counts: dict[str, int] = {}
        try:
            xml_text = await self.client.get_text(
                url,
                headers={"User-Agent": UA, "Accept": "application/atom+xml, */*"},
            )
        except Exception as exc:
            LOG.warning("reddit_rss r/%s: %s", sub, str(exc)[:120])
            return counts

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            LOG.warning("reddit_rss r/%s parse: %s", sub, exc)
            return counts

        # Atom feed (Reddit RSS)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entries = root.findall("a:entry", ns) or root.findall("entry")
        for entry in entries:
            title = entry.findtext("{http://www.w3.org/2005/Atom}title") or entry.findtext("title") or ""
            summary = entry.findtext("{http://www.w3.org/2005/Atom}summary") or entry.findtext("summary") or ""
            updated = (
                entry.findtext("{http://www.w3.org/2005/Atom}updated")
                or entry.findtext("updated")
                or entry.findtext("pubDate")
                or ""
            )
            try:
                dt = parsedate_to_datetime(updated) if "GMT" in updated or "," in updated else datetime.fromisoformat(
                    updated.replace("Z", "+00:00")
                )
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt.timestamp() < cutoff_ts:
                    continue
            except Exception:
                pass  # tarih parse edilemezse yine de say (yeni olabilir)

            blob = f"{title}\n{summary}"
            for t in self._extract(blob):
                counts[t] = counts.get(t, 0) + 1
        return counts

    async def poll(self, ctx) -> None:
        self._reset_run()
        cutoff_ts = time.time() - LOOKBACK_SEC
        totals: dict[str, int] = {}

        for sub in SUBREDDITS:
            sub_counts = await self._fetch_sub(sub, cutoff_ts)
            for k, v in sub_counts.items():
                totals[k] = totals.get(k, 0) + v

        emitted = 0
        for ticker, count in totals.items():
            if count <= 0:
                continue
            await self._emit(
                ticker=ticker,
                value=float(count),
                metadata={
                    "mentions_1h": count,
                    "subreddits": list(SUBREDDITS),
                    "source": "reddit_public_rss",
                },
                url=f"https://www.reddit.com/search/?q=%24{ticker}&sort=new",
                event_id=f"{ticker}-rss-{int(time.time()) // LOOKBACK_SEC}",
            )
            emitted += 1

        LOG.info("[reddit_rss] subs=%d tickers=%d mentions=%d emitted=%d",
                 len(SUBREDDITS), len(totals), sum(totals.values()), emitted)


async def poll(ctx) -> None:
    await _get_singleton().poll(ctx)


_singleton: Optional[RedditRSSScanner] = None


def _get_singleton() -> RedditRSSScanner:
    global _singleton
    if _singleton is None:
        _singleton = RedditRSSScanner()
    return _singleton
