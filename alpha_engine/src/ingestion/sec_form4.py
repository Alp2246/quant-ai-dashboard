"""
SECForm4Scanner - Insider buying erken uyari (en guclu alpha sinyallerinden).

Form 4 nedir?
    SEC Form 4 = "Statement of Changes in Beneficial Ownership".
    Yonetici/CEO/CFO/Direktor hisse alip-sattiginda 2 IS GUNU icinde
    SEC'e dosyalanmasi ZORUNLU. 10% pay sahipleri de dahil.

Neden onemli?
    CEO/CFO kendi parasiyla hisse ALIRSA (Purchase, "P" kodu):
    -> Sirketin gelecegine olan inanci. Genelde haberden ONCE olur.
    -> Stok-opsiyon esitleri (A/F/M) sayilmaz, sadece "P" = nakit alim.
    Insider SATIS'i (S) NORMAL: maas, vergi, hayat - alpha sinyali degil.

Strateji:
    1. Her ticker icin EDGAR atom feed'i (type=4) - son 20 filing.
    2. Yeni accession_id'leri (dedup) icin primary_doc.xml indir.
    3. Transaction code "P" ise (Purchase): emit signal.
       value = USD aliminin log-olcekli degeri (1k=1, 10k=2, 100k=3 ...).
    4. Insider'in unvanini metadata'ya yaz (CEO/CFO bonus).

Rate limit:
    SEC global 10 req/sec. Cluster icin ticker basina max 3 yeni XML/cycle.
"""
from __future__ import annotations

import logging
import math
import re
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
ATOM_URL = ("https://www.sec.gov/cgi-bin/browse-edgar"
            "?action=getcompany&CIK={cik}&type=4&dateb=&owner=include"
            "&count={n}&output=atom")

# Filing detayi XML cinde gecen transaction kodlari
PURCHASE_CODES = frozenset({"P"})        # nakit, open-market alim - kanonik
NEUTRAL_CODES = frozenset({"A", "M", "F", "G", "I"})  # opsiyon/vergi - sayilmaz
SALE_CODES = frozenset({"S", "D"})

# Insider rolu bonus carpan
OFFICER_BONUS = {
    "CEO": 1.5, "CFO": 1.4, "COO": 1.3, "PRESIDENT": 1.5,
    "CHAIRMAN": 1.3, "FOUNDER": 1.4, "10%": 0.9, "DIRECTOR": 1.0,
}

# Accession_id formati: 1234567890-AA-BBBBBB (18 char)
_ACC_RE = re.compile(r"\d{10}-\d{2}-\d{6}")

# Form4 XML namespace yok - direkt tag'lerle
def _f4_findtext(elem, *path, default=""):
    cur = elem
    for tag in path:
        cur = cur.find(tag) if cur is not None else None
        if cur is None:
            return default
    return (cur.text or "").strip()


class SECForm4Scanner(BaseScanner):
    name = "sec_form4"

    def __init__(self, *, per_ticker_limit: int = 20,
                 max_new_xml_per_ticker: int = 3) -> None:
        super().__init__()
        self.per_ticker_limit = per_ticker_limit
        self.max_new_xml = max_new_xml_per_ticker
        self.user_agent = settings.SEC_USER_AGENT or "QuantAI test@example.com"
        self.client = get_http_client()
        # SEC global rate limit; ozellikle XML indirme cok ekler
        self.client.set_rate_limit(HOST, calls=8, per_seconds=1.0)
        self._cik_map: dict[str, str] = {}

    async def _ensure_cik_map(self) -> None:
        if self._cik_map:
            return
        cache = settings.STATE_DIR / "ticker_cik.json"
        self._cik_map = await load_ticker_to_cik(cache, self.user_agent)

    async def _fetch_atom(self, ticker: str, cik: str) -> list[dict]:
        url = ATOM_URL.format(cik=cik, n=self.per_ticker_limit)
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
            LOG.warning("%s Form4 atom err: %s", ticker, str(exc)[:120])
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        out = []
        for entry in root.findall("a:entry", ATOM_NS):
            title = (entry.findtext("a:title", default="", namespaces=ATOM_NS) or "").strip()
            updated = (entry.findtext("a:updated", default="", namespaces=ATOM_NS) or "").strip()
            link_el = entry.find("a:link", ATOM_NS)
            href = link_el.get("href") if link_el is not None else None
            acc_id = None
            if href:
                m = _ACC_RE.search(href)
                if m:
                    acc_id = m.group(0)
            try:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except Exception:
                ts = datetime.now(timezone.utc)
            out.append({
                "title": title, "index_url": href,
                "accession_id": acc_id, "timestamp": ts,
            })
        return out

    async def _fetch_primary_xml(self, cik: str, accession_id: str) -> Optional[ET.Element]:
        """
        Form 4 primary XML genelde 'primary_doc.xml' adi altinda durur.
        Acession_id (1234567890-AA-BBBBBB) -> path: 1234567890AABBBBBB
        """
        acc_clean = accession_id.replace("-", "")
        cik_int = str(int(cik))  # leading zero strip
        url = (f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
               f"{acc_clean}/primary_doc.xml")
        try:
            xml_text = await self.client.get_text(
                url,
                headers={"User-Agent": self.user_agent, "Host": HOST},
            )
            return ET.fromstring(xml_text)
        except Exception as exc:
            LOG.debug("primary_doc.xml indirme hata %s/%s: %s",
                      cik_int, accession_id, str(exc)[:80])
            return None

    @staticmethod
    def _parse_form4(root: ET.Element) -> dict:
        """
        Form 4 XML'inden insider + transactions cikar.
        Donus:
            {
              "insider_name": "JOHN SMITH",
              "insider_titles": ["CEO"],
              "is_director": True/False,
              "transactions": [
                  {"code": "P", "shares": 1000, "price": 50.0, "value_usd": 50000}
              ],
              "purchase_usd": 50000,    # P kodlarinin toplami
              "sale_usd": 0,
            }
        """
        owner = root.find("reportingOwner")
        insider_name = _f4_findtext(owner, "reportingOwnerId", "rptOwnerName") if owner is not None else ""
        rel = owner.find("reportingOwnerRelationship") if owner is not None else None
        is_officer = _f4_findtext(rel, "isOfficer") == "1" if rel is not None else False
        is_director = _f4_findtext(rel, "isDirector") == "1" if rel is not None else False
        is_10pct = _f4_findtext(rel, "isTenPercentOwner") == "1" if rel is not None else False
        officer_title = _f4_findtext(rel, "officerTitle") if rel is not None else ""

        titles = []
        if officer_title:
            titles.append(officer_title.upper())
        if is_director:
            titles.append("DIRECTOR")
        if is_10pct:
            titles.append("10%")

        transactions = []
        purchase_usd = 0.0
        sale_usd = 0.0
        for tbl_tag in ("nonDerivativeTable", "derivativeTable"):
            tbl = root.find(tbl_tag)
            if tbl is None:
                continue
            for tx in list(tbl):
                if not tx.tag.endswith("Transaction"):
                    continue
                code = _f4_findtext(tx, "transactionCoding", "transactionCode")
                shares_s = _f4_findtext(tx, "transactionAmounts", "transactionShares", "value")
                price_s = _f4_findtext(tx, "transactionAmounts", "transactionPricePerShare", "value")
                try:
                    shares = float(shares_s)
                except ValueError:
                    shares = 0.0
                try:
                    price = float(price_s)
                except ValueError:
                    price = 0.0
                value_usd = shares * price
                transactions.append({
                    "code": code, "shares": shares,
                    "price": price, "value_usd": value_usd,
                })
                if code in PURCHASE_CODES:
                    purchase_usd += value_usd
                elif code in SALE_CODES:
                    sale_usd += value_usd

        return {
            "insider_name": insider_name,
            "insider_titles": titles,
            "is_officer": is_officer,
            "is_director": is_director,
            "transactions": transactions,
            "purchase_usd": purchase_usd,
            "sale_usd": sale_usd,
        }

    @staticmethod
    def _value_score(purchase_usd: float, titles: list[str]) -> float:
        """USD alim degerini log-olcekte score'a cevirir + insider rolu bonusu."""
        if purchase_usd <= 0:
            return 0.0
        # 1k=1, 10k=2, 100k=3, 1M=4, 10M=5
        base = math.log10(max(purchase_usd, 1_000)) - 2
        bonus = max((OFFICER_BONUS.get(t, 1.0) for t in titles), default=1.0)
        # Title'in icinde "CEO" gibi sub-string varsa da yakala
        for t in titles:
            for key, b in OFFICER_BONUS.items():
                if key in t and b > bonus:
                    bonus = b
        return round(base * bonus, 2)

    async def poll(self, ctx) -> None:
        self._reset_run()
        await self._ensure_cik_map()
        if not self._cik_map:
            return

        tickers = settings.TICKERS
        n_emitted = 0
        n_dedup = 0
        n_xml_fetched = 0
        n_purchases = 0

        for ticker in tickers:
            cik = self._cik_map.get(ticker.upper())
            if not cik:
                continue
            atom_entries = await self._fetch_atom(ticker, cik)
            if not atom_entries:
                continue

            # En yeni N tanesi icin sadece dedup-yenilerini XML olarak indir.
            new_count = 0
            for entry in atom_entries:
                if new_count >= self.max_new_xml:
                    break
                acc_id = entry.get("accession_id")
                if not acc_id:
                    continue
                event_id = f"{ticker}:F4:{acc_id}"
                # Bus dedup kontrolu: yeni mi?
                if self.bus.contains_event(event_id):
                    n_dedup += 1
                    continue

                # XML indir + parse
                xml_root = await self._fetch_primary_xml(cik, acc_id)
                n_xml_fetched += 1
                if xml_root is None:
                    # Yine de filing var: minimal not olarak emit (value=0.5)
                    await self._emit(
                        ticker=ticker, value=0.5,
                        metadata={
                            "title": entry["title"][:200],
                            "form": "4",
                            "filed_at": entry["timestamp"].isoformat(),
                            "parse_status": "xml_missing",
                        },
                        url=entry.get("index_url"),
                        event_id=event_id,
                    )
                    n_emitted += 1
                    new_count += 1
                    continue

                parsed = self._parse_form4(xml_root)
                purchase_usd = parsed["purchase_usd"]
                sale_usd = parsed["sale_usd"]
                titles = parsed["insider_titles"]

                # Sadece PURCHASE sinyal degeri tasir
                if purchase_usd > 0:
                    score = self._value_score(purchase_usd, titles)
                    insider = parsed["insider_name"][:80]
                    title_str = ", ".join(titles[:3]) or "Insider"
                    desc = (f"INSIDER BUY: {title_str} {insider} "
                            f"${purchase_usd:,.0f} aldi")
                    await self._emit(
                        ticker=ticker, value=score,
                        metadata={
                            "title": desc[:200],
                            "form": "4",
                            "filed_at": entry["timestamp"].isoformat(),
                            "purchase_usd": purchase_usd,
                            "insider_name": insider,
                            "insider_titles": titles,
                            "transactions": parsed["transactions"][:5],
                        },
                        url=entry.get("index_url"),
                        event_id=event_id,
                    )
                    n_emitted += 1
                    n_purchases += 1
                else:
                    # Sale veya sadece option exercise - sinyal degil
                    # Ama dedup'a girsin: tekrar XML indirmeyelim
                    await self._emit(
                        ticker=ticker, value=0.0,
                        metadata={
                            "title": "Form 4 (non-purchase)",
                            "form": "4",
                            "filed_at": entry["timestamp"].isoformat(),
                            "sale_usd": sale_usd,
                            "parse_status": "non_purchase",
                        },
                        url=entry.get("index_url"),
                        event_id=event_id,
                    )
                new_count += 1

        LOG.info("[sec_form4] tickers=%d xml_fetched=%d purchases=%d emitted=%d dedup=%d",
                 len(tickers), n_xml_fetched, n_purchases, n_emitted, n_dedup)


async def poll(ctx) -> None:
    scanner = _get_singleton()
    await scanner.poll(ctx)


_singleton: Optional[SECForm4Scanner] = None


def _get_singleton() -> SECForm4Scanner:
    global _singleton
    if _singleton is None:
        _singleton = SECForm4Scanner()
    return _singleton
