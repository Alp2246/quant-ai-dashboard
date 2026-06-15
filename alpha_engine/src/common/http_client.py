"""
http_client - aiohttp wrapper (retry, concurrency, rate limit).

Tasarim:
    * Tek paylasilan ClientSession (modul seviyesi)
    * Semaphore ile global concurrency limiti
    * Per-host rate limit (token bucket)
    * Otomatik retry: 429, 5xx, timeout -> exponential backoff
    * Gracef shutdown: aclose()

Kullanim:
    client = get_http_client()
    data = await client.get_json("https://api.example.com/v1/x", headers={...})
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import aiohttp

LOG = logging.getLogger(__name__)


class RateLimiter:
    """Basit token bucket - calls/per_seconds."""
    def __init__(self, calls: int, per_seconds: float):
        self.calls = max(1, int(calls))
        self.per_seconds = max(0.1, float(per_seconds))
        self._tokens = float(self.calls)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._last = now
            self._tokens = min(self.calls,
                               self._tokens + elapsed * (self.calls / self.per_seconds))
            if self._tokens < 1:
                wait = (1 - self._tokens) * (self.per_seconds / self.calls)
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1


class HttpClient:
    def __init__(self, *, concurrency: int = 8, timeout: int = 20,
                 max_retries: int = 3):
        self.concurrency = concurrency
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self._sema = asyncio.Semaphore(concurrency)
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiters: dict[str, RateLimiter] = {}

    def set_rate_limit(self, host: str, calls: int, per_seconds: float) -> None:
        self._rate_limiters[host] = RateLimiter(calls, per_seconds)

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=self.concurrency * 2,
                                              ttl_dns_cache=300)
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector,
                raise_for_status=False,
            )
        return self._session

    @staticmethod
    def _parse_retry_after(value: str) -> Optional[float]:
        """RFC 7231: int saniye veya HTTP-date. None ise dondurmez."""
        if not value:
            return None
        v = value.strip()
        # 1) Int saniye?
        try:
            n = float(v)
            if n >= 0:
                return min(n, 300.0)  # 5 dakika tavanli
        except ValueError:
            pass
        # 2) HTTP-date (Sun, 06 Nov 1994 08:49:37 GMT)
        try:
            from email.utils import parsedate_to_datetime
            from datetime import datetime, timezone
            dt = parsedate_to_datetime(v)
            if dt is None:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = (dt - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, min(delta, 300.0))
        except Exception:
            return None

    async def _request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        session = await self._ensure_session()
        host = url.split("/", 3)[2] if "://" in url else ""
        rl = self._rate_limiters.get(host)
        if rl:
            await rl.acquire()

        last_exc: Optional[Exception] = None
        consecutive_429 = 0
        # 429'lar icin daha agresif (cunku rate-limit cezasini geri almak zaman alir)
        max_attempts = max(self.max_retries, 5)

        for attempt in range(max_attempts):
            try:
                async with self._sema:
                    resp = await session.request(method, url, **kwargs)

                # 429: Retry-After'a oncelik ver, agresif backoff
                if resp.status == 429:
                    consecutive_429 += 1
                    retry_after = self._parse_retry_after(
                        resp.headers.get("Retry-After", "")
                    )
                    await resp.release()

                    if retry_after is not None:
                        backoff = retry_after
                        reason = f"Retry-After={backoff:.1f}s"
                    else:
                        # exponential: 2s, 4s, 8s, 16s, 32s, 60s tavan
                        backoff = min(60.0, 2.0 * (2 ** consecutive_429))
                        reason = f"backoff={backoff:.1f}s"
                    LOG.warning(
                        "HTTP 429 RATE-LIMIT %s -> wait %s (try %d/%d)",
                        host, reason, attempt + 1, max_attempts,
                    )
                    await asyncio.sleep(backoff)
                    continue

                # 5xx: gecici, standart backoff
                if resp.status in (500, 502, 503, 504):
                    body_snippet = (await resp.text())[:200]
                    await resp.release()
                    backoff = min(30.0, 0.5 * (2 ** attempt))
                    LOG.warning("HTTP %d %s -> retry %d/%d after %.1fs (%s)",
                                resp.status, url, attempt + 1, max_attempts,
                                backoff, body_snippet)
                    await asyncio.sleep(backoff)
                    continue

                return resp

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                backoff = min(30.0, 0.5 * (2 ** attempt))
                LOG.warning("HTTP err %s %s -> retry %d/%d after %.1fs",
                            type(exc).__name__, url, attempt + 1, max_attempts,
                            backoff)
                await asyncio.sleep(backoff)

        raise RuntimeError(f"HTTP failed after {max_attempts} retries: {url}") \
            from last_exc

    async def get_json(self, url: str, **kwargs) -> Any:
        resp = await self._request("GET", url, **kwargs)
        async with resp:
            if resp.status >= 400:
                body = (await resp.text())[:300]
                raise RuntimeError(f"HTTP {resp.status} {url}: {body}")
            return await resp.json(content_type=None)

    async def get_text(self, url: str, **kwargs) -> str:
        resp = await self._request("GET", url, **kwargs)
        async with resp:
            if resp.status >= 400:
                body = (await resp.text())[:300]
                raise RuntimeError(f"HTTP {resp.status} {url}: {body}")
            return await resp.text()

    async def aclose(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None


_singleton: Optional[HttpClient] = None


def get_http_client() -> HttpClient:
    global _singleton
    if _singleton is None:
        from config import settings
        _singleton = HttpClient(
            concurrency=settings.HTTP_CONCURRENCY,
            timeout=settings.HTTP_TIMEOUT,
            max_retries=settings.HTTP_MAX_RETRIES,
        )
    return _singleton
