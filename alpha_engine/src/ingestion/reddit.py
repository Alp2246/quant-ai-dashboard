"""
RedditScanner - r/wallstreetbets + r/stocks ticker mention sayaci.

Strateji:
    Her subreddit'ten son 1 saatlik post + comment'leri cek, ticker
    mention'larini say. mention spike -> retail dalgasi yaklasiyor.

Ticker tespiti:
    - $TICKER veya boslukla cevrili TICKER (case-sensitive)
    - Yaygin ingilizce kelimelerle catismayi onlemek icin BLOCKLIST var
      (AI, IT, BE, GO, ON, IS gibi tek-iki harf kelimeler)
    - Sadece settings.TICKERS icindeki ticker'lar sayilir

Bagimlilik:
    asyncpraw (Reddit'in resmi destekledigi async client)
    pip install asyncpraw

ATAMA YAPILMAMISSA:
    REDDIT_CLIENT_ID / SECRET yoksa DISABLED loglar.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional

from config import settings
from src.ingestion.base import BaseScanner

LOG = logging.getLogger(__name__)

SUBREDDITS = ("wallstreetbets", "stocks", "stockmarket", "investing", "options")
LOOKBACK_SEC = 3600                  # son 1 saat
POSTS_PER_SUB = 80                    # her subreddit son 80 post
MAX_COMMENTS_PER_POST = 30
BLOCKLIST = {
    "A", "I", "AI", "IT", "BE", "GO", "ON", "IS", "OR", "AT", "TO", "DO",
    "ALL", "ANY", "ARE", "FOR", "GET", "NEW", "NOW", "ONE", "OUT", "THE",
    "TWO", "WAY", "WHO", "YES", "EOD", "EOM", "EOY", "ETF", "PSA", "PRE",
    "BTW", "IMO", "IPO", "DD", "CEO", "CFO", "ATH", "ATL", "OP", "FYI",
    "USA", "USD", "EUR", "GDP", "API", "SDK", "OTC", "PT", "PE",
}


class RedditScanner(BaseScanner):
    name = "reddit"

    def __init__(self) -> None:
        super().__init__()
        self._reddit = None
        self._ticker_set: set[str] = {t.upper() for t in settings.TICKERS}
        # Regex: $TICKER veya kelime sinirlari icinde 2-5 buyuk harf
        self._re_dollar = re.compile(r"\$([A-Z]{1,6})\b")
        self._re_word = re.compile(r"\b([A-Z]{2,6})\b")

    async def _ensure_client(self):
        if self._reddit is not None:
            return self._reddit
        if not (settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET):
            return None
        try:
            import asyncpraw  # noqa: PLC0415
        except ImportError:
            LOG.error("asyncpraw yuklu degil: pip install asyncpraw")
            return None
        self._reddit = asyncpraw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT or "quantai-alpha/0.1",
            read_only=True,
            check_for_async=False,
        )
        return self._reddit

    def _extract_tickers(self, text: str) -> set[str]:
        if not text:
            return set()
        # Hizli filter: hic dolar isareti veya buyuk harf yoksa cik
        found = set()
        for m in self._re_dollar.finditer(text):
            t = m.group(1).upper()
            if t in self._ticker_set and t not in BLOCKLIST:
                found.add(t)
        for m in self._re_word.finditer(text):
            t = m.group(1).upper()
            if t in self._ticker_set and t not in BLOCKLIST:
                found.add(t)
        return found

    async def _scan_subreddit(self, sub_name: str, cutoff: float) -> dict[str, int]:
        """Returns ticker -> mention count."""
        counts: dict[str, int] = {}
        try:
            sub = await self._reddit.subreddit(sub_name)
            async for post in sub.new(limit=POSTS_PER_SUB):
                if post.created_utc < cutoff:
                    continue
                text = f"{post.title or ''}\n{post.selftext or ''}"
                for t in self._extract_tickers(text):
                    counts[t] = counts.get(t, 0) + 1
                # Yorumlari kismi tara
                try:
                    await post.load()
                    comments = post.comments
                    # asyncpraw'da replace_more cagrisi yapilabilir ama yavas;
                    # mevcut top-level yorumlari kullanmak yeterli sinyal verir.
                    for c in list(comments)[:MAX_COMMENTS_PER_POST]:
                        body = getattr(c, "body", None)
                        if not body:
                            continue
                        if getattr(c, "created_utc", 0) < cutoff:
                            continue
                        for t in self._extract_tickers(body):
                            counts[t] = counts.get(t, 0) + 1
                except Exception:
                    continue
        except Exception as exc:
            LOG.warning("reddit subreddit '%s' err: %s", sub_name, str(exc)[:200])
        return counts

    async def poll(self, ctx) -> None:
        self._reset_run()
        reddit = await self._ensure_client()
        if reddit is None:
            LOG.debug("reddit: client yok (REDDIT_CLIENT_ID/SECRET eksik?)")
            return

        cutoff = time.time() - LOOKBACK_SEC
        totals: dict[str, int] = {}
        for sub in SUBREDDITS:
            sub_counts = await self._scan_subreddit(sub, cutoff)
            for k, v in sub_counts.items():
                totals[k] = totals.get(k, 0) + v

        emitted = 0
        # Sadece >= 1 mention'lu ticker'lari yaz
        for ticker, count in totals.items():
            if count <= 0:
                continue
            await self._emit(
                ticker=ticker,
                value=float(count),
                metadata={
                    "lookback_sec": LOOKBACK_SEC,
                    "subreddits": list(SUBREDDITS),
                },
            )
            emitted += 1

        LOG.info("[reddit] mentions tickers=%d toplam_mention=%d emitted=%d",
                 len(totals), sum(totals.values()), emitted)

    async def aclose(self) -> None:
        if self._reddit is not None:
            try:
                await self._reddit.close()
            except Exception:
                pass


async def poll(ctx) -> None:
    scanner = _get_singleton()
    await scanner.poll(ctx)


_singleton: Optional[RedditScanner] = None


def _get_singleton() -> RedditScanner:
    global _singleton
    if _singleton is None:
        _singleton = RedditScanner()
    return _singleton
