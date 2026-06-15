"""
SECScanner - SEC EDGAR canli Atom feed tarayici.

Strateji:
    1. EDGAR'in /cgi-bin/browse-edgar full-text-current-events Atom feed'i
       son saatlerin TUM filing'lerini doner.
    2. Sadece form type = 8-K (material event - en hizli alpha sinyal kaynagi)
    3. Her ticker icin son gorulen accession_id state dosyasinda saklanir
       -> dedup ve tekrar bildirim engellenir.
    4. Her yeni 8-K = 1 sinyal (value=1.0). Birden fazla 8-K = velocity.
    5. SignalBus uzerinden yayinlanir; analytics modulu (Adim 3) bunu
       z-score'a cevirecek.

API:
    * /cgi-bin/browse-edgar?action=getcompany&CIK=XXX&type=8-K&output=atom
      (her ticker icin son N filing - en saglam yontem)
    * Limit: 10 req/sec (SEC), User-Agent zorunlu.

References:
    https://www.sec.gov/os/accessing-edgar-data
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

from config import settings
from src.common.http_client import get_http_client
from src.common.ticker_map import load_ticker_to_cik
from src.ingestion.base import BaseScanner

LOG = logging.getLogger(__name__)
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
HOST = "www.sec.gov"
URL = ("https://www.sec.gov/cgi-bin/browse-edgar"
       "?action=getcompany&CIK={cik}&type={form}&dateb=&owner=include&count={n}&output=atom")


class SECScanner(BaseScanner):
    name = "sec_edgar"

    def __init__(self, *, forms: tuple[str, ...] = ("8-K",),
                 per_ticker_limit: int = 10) -> None:
        super().__init__()
        self.forms = forms
        self.per_ticker_limit = per_ticker_limit
        self.user_agent = settings.SEC_USER_AGENT or "QuantAI test@example.com"
        self.client = get_http_client()
        # SEC rate limit: <10 req/sec global
        self.client.set_rate_limit(HOST, calls=8, per_seconds=1.0)
        self._cik_map: dict[str, str] = {}

    async def _ensure_cik_map(self) -> None:
        if self._cik_map:
            return
        cache = settings.STATE_DIR / "ticker_cik.json"
        self._cik_map = await load_ticker_to_cik(cache, self.user_agent)

    async def _fetch_filings(self, ticker: str, cik: str, form: str) -> list[dict]:
        url = URL.format(cik=cik, form=form, n=self.per_ticker_limit)
        try:
            xml_text = await self.client.get_text(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/atom+xml",
                    "Host": HOST,
                },
            )
        except Exception as exc:
            LOG.warning("%s [%s] EDGAR fetch err: %s", ticker, form, exc)
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            LOG.warning("%s atom parse err: %s", ticker, exc)
            return []

        out = []
        for entry in root.findall("a:entry", ATOM_NS):
            title = (entry.findtext("a:title", default="", namespaces=ATOM_NS) or "").strip()
            updated = (entry.findtext("a:updated", default="", namespaces=ATOM_NS) or "").strip()
            link_el = entry.find("a:link", ATOM_NS)
            href = link_el.get("href") if link_el is not None else None
            # accession_id: link icinde -> .../Archives/edgar/data/CIK/0001234567-25-000123-index.htm
            acc_id: Optional[str] = None
            if href:
                for tok in href.replace("/", " ").split():
                    if tok.count("-") == 2 and len(tok) >= 18 and tok[:10].isdigit():
                        acc_id = tok
                        break
            try:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except Exception:
                ts = datetime.now(timezone.utc)
            out.append({
                "title": title, "url": href, "accession_id": acc_id, "timestamp": ts,
                "form": form,
            })
        return out

    async def poll(self, ctx) -> None:
        self._reset_run()
        await self._ensure_cik_map()
        if not self._cik_map:
            LOG.warning("ticker_cik haritasi bos; SEC scanner pas geciyor")
            return

        tickers = settings.TICKERS
        n_emitted = 0
        n_skipped_dedup = 0
        n_no_cik = 0

        for ticker in tickers:
            cik = self._cik_map.get(ticker.upper())
            if not cik:
                n_no_cik += 1
                continue
            for form in self.forms:
                filings = await self._fetch_filings(ticker, cik, form)
                if not filings:
                    continue
                for f in filings:
                    event_id = f["accession_id"] or f"{ticker}-{form}-{f['timestamp'].isoformat()}"
                    emitted = await self._emit(
                        ticker=ticker,
                        value=1.0,
                        metadata={
                            "title": f["title"][:200],
                            "form": form,
                            "filed_at": f["timestamp"].isoformat(),
                        },
                        url=f["url"],
                        event_id=f"{ticker}:{event_id}",
                    )
                    if emitted:
                        n_emitted += 1
                    else:
                        n_skipped_dedup += 1

        LOG.info("[sec_edgar] tickers=%d emitted=%d dedup=%d no_cik=%d",
                 len(tickers), n_emitted, n_skipped_dedup, n_no_cik)


async def poll(ctx) -> None:
    """Module-level entry point - orchestrator burayi cagirir."""
    scanner = _get_singleton()
    await scanner.poll(ctx)


_singleton: Optional[SECScanner] = None


def _get_singleton() -> SECScanner:
    global _singleton
    if _singleton is None:
        _singleton = SECScanner()
    return _singleton
