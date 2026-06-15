"""
ticker_validator - sosyal medya metinlerinden gercek ticker cikarir.

Iki katman:
    1) BLOCKLIST - yaygin Ingilizce kelimeler/kısaltmalar (DD, YOLO, A, FOR, CEO...)
    2) Master list - SEC'in resmi NASDAQ + NYSE listesi (ticker_map.py)
                     URL: https://www.sec.gov/files/company_tickers.json
                     ~10,500 gercek US ticker

Kullanim:
    from src.common.ticker_validator import extract_tickers, is_valid_ticker
    found = extract_tickers("Just bought $AXTI today, also IONQ DD")
    # -> {"AXTI", "IONQ"}     DD elenir (yaygin kisaltma)
    #                          A da elenir (1-harf + yaygin)

Performans:
    Master list bir kere disk'ten yuklenir, bellekte set olarak tutulur.
    O(1) lookup; binlerce mesaj/sn isleyebilir.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable, Optional

LOG = logging.getLogger(__name__)


# ===========================================================================
#  Yaygin Ingilizce kelimeler + finans kisaltmalari
#  Hepsi gercek ticker olabilir (A, NEW, ALL, FOR) ama sosyal medyada %99
#  kelime olarak gectikleri icin SUFFIX olmadan ($ olmadan) elenir.
# ===========================================================================
BLOCKLIST = frozenset({
    # Tek harfli ve yaygin
    "A", "I", "X", "T", "M", "F", "B", "C", "D", "E", "G", "H", "J", "K",
    "L", "N", "O", "P", "Q", "R", "S", "U", "V", "W", "Y", "Z",
    # 2-3 harfli yaygin Ingilizce
    "AI", "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IF", "IN",
    "IS", "IT", "ME", "MY", "NO", "OF", "ON", "OR", "SO", "TO", "UP", "US",
    "WE", "ALL", "AND", "ANY", "ARE", "BAD", "BIG", "BUT", "BUY", "CAN",
    "DID", "EOD", "EOM", "EOY", "FOR", "GET", "GOT", "HAS", "HOT", "ITS",
    "LET", "MAD", "MUCH", "NEW", "NOT", "NOW", "ODD", "OUR", "OUT", "OWN",
    "PUT", "RUN", "SEE", "SET", "TAX", "THE", "TWO", "USE", "WAS", "WAY",
    "WHO", "WHY", "WIN", "YES", "YET", "YOU",
    # 4-5 harf yaygin
    "ABOUT", "AFTER", "ALSO", "BACK", "BEEN", "BEFORE", "BEST", "BOTH",
    "CALL", "CASH", "DATA", "DAYS", "DEAL", "DID", "EACH", "EVEN", "EVER",
    "FAIR", "FAST", "FEEL", "FELT", "FIND", "FIVE", "FOUR", "FREE", "FROM",
    "FULL", "GAVE", "GAIN", "GIVE", "GOLD", "GONE", "GOOD", "HALT", "HAVE",
    "HERE", "HIGH", "HOLD", "HOPE", "HUGE", "IDEA", "INTO", "JUST", "KEEP",
    "KIND", "KNOW", "LAST", "LATE", "LESS", "LIFE", "LIFT", "LIKE", "LINE",
    "LIVE", "LONG", "LOOK", "LOSE", "LOSS", "LOST", "LOTS", "LOVE", "MADE",
    "MAKE", "MANY", "MORE", "MOST", "MOVE", "MUCH", "MUST", "NEED", "NEXT",
    "NICE", "NONE", "ONCE", "ONLY", "OPEN", "OVER", "PAID", "PART", "PICK",
    "PLAY", "PLUS", "POST", "PUSH", "REAL", "ROOM", "SAID", "SAME", "SAVE",
    "SEEN", "SELL", "SENT", "SHOP", "SHOT", "SHOW", "SIDE", "SIZE", "SOLD",
    "SOME", "SOON", "STOP", "SUCH", "SURE", "TAKE", "TALK", "TEAM", "TELL",
    "THAN", "THAT", "THEM", "THEN", "THEY", "THIS", "THUS", "TIME", "TODAY",
    "TOLD", "TOOK", "TRUE", "TYPE", "USED", "USES", "VERY", "VIEW", "WANT",
    "WEEK", "WELL", "WENT", "WERE", "WHAT", "WHEN", "WILL", "WITH", "WORK",
    "YEAR", "YOUR",
    # Finans / Reddit jargonu
    "ATH", "ATL", "API", "APY", "APR", "BTC", "BTW", "CEO", "CFO", "COO",
    "CTO", "DCF", "DD", "EPS", "ETF", "ETH", "FAQ", "FED", "FOMC", "FUD",
    "FYI", "GDP", "HFT", "HODL", "IMHO", "IMO", "IPO", "IRA", "IRS", "ISIN",
    "JOMO", "LOL", "LULZ", "MOON", "NFA", "OK", "OP", "OTC", "OTM", "PE",
    "PEG", "PR", "PSA", "PT", "PTM", "QA", "REIT", "ROFL", "ROI", "ROIC",
    "SEC", "SMH", "SMS", "SP", "SPY", "SUS", "TBH", "TIA", "TLDR", "TLDR",
    "TOS", "USA", "USD", "USDT", "VC", "VOO", "VTI", "VWAP", "WSB", "XD",
    "YOLO", "YTD", "EOY", "EOM", "EOD", "PM", "AM", "ET", "EST", "PST",
    "GMT", "FAA", "FCC", "FAIR", "FAANG", "ESG", "PE", "PR",
    # Sirket olabilir ama yaygin kelime - ozellikle $ olmadan elenir
    "OPEN", "PLAY", "FORM", "PATH", "ROOT", "PROG", "MASS", "RING",
    "GROW", "PLUS", "PASS", "MATE", "ROOM", "TIME", "WORK",
    "TRUE", "TYPE",
    # Tekrar / Dolu sembol toplulugu (Cline, Reddit emoji sevenler)
    "WAGMI", "NGMI", "HODL", "REKT", "DEGENS", "DEGEN",
})


# Regex: $TICKER tercih edilir; kelime sinirinda da yakalanir
_RE_DOLLAR = re.compile(r"\$([A-Z]{1,6})\b")
_RE_WORD = re.compile(r"\b([A-Z]{2,6})\b")


# ===========================================================================
#  TickerValidator
# ===========================================================================
class TickerValidator:
    def __init__(self, master_path: Path,
                 universe: Optional[set[str]] = None) -> None:
        self.master_path = master_path
        # Master list (ticker_map.py cache'inden okur). Yoksa universe ile devam.
        self._master: set[str] = set()
        self._loaded = False
        # Eğer kullanıcı belirli evren verdiyse SADECE onu kabul et
        self._universe: Optional[set[str]] = (
            {t.upper() for t in universe} if universe else None
        )

    def _load_master(self) -> None:
        if self._loaded:
            return
        if not self.master_path.is_file():
            LOG.debug("ticker master list yok: %s", self.master_path)
            self._loaded = True
            return
        try:
            data = json.loads(self.master_path.read_text(encoding="utf-8"))
            # ticker_map formati: {"AAPL": "0000320193", ...}
            self._master = {k.upper() for k in data.keys()}
            LOG.info("TickerValidator master list: %d ticker", len(self._master))
        except Exception as exc:
            LOG.warning("master list okuma: %s", exc)
        self._loaded = True

    def is_valid_ticker(self, candidate: str, *, dollar_prefixed: bool = False) -> bool:
        """
        - BLOCKLIST'teyse: $ prefix yoksa elenir, $ varsa kabul (kasıtlı yazılmış)
        - Universe sınırı varsa içinde olmalı
        - Aksi halde master list'te olmalı
        """
        c = candidate.upper().strip()
        if not c or len(c) < 1 or len(c) > 6:
            return False
        if not c.isalpha():
            return False

        # BLOCKLIST: sadece $ prefix yoksa el
        if c in BLOCKLIST and not dollar_prefixed:
            return False

        # Universe sınırı varsa öncelik
        if self._universe is not None:
            return c in self._universe

        # Master list
        self._load_master()
        if self._master:
            return c in self._master

        # Master yoksa konservatif: BLOCKLIST disindaki her sey kabul
        return True

    def extract_tickers(self, text: str) -> set[str]:
        """Metinden gecerli ticker'lari cikarir."""
        if not text:
            return set()
        found: set[str] = set()
        for m in _RE_DOLLAR.finditer(text):
            t = m.group(1).upper()
            if self.is_valid_ticker(t, dollar_prefixed=True):
                found.add(t)
        for m in _RE_WORD.finditer(text):
            t = m.group(1).upper()
            if self.is_valid_ticker(t, dollar_prefixed=False):
                found.add(t)
        return found


# ===========================================================================
#  Singleton
# ===========================================================================
_validator: Optional[TickerValidator] = None


def get_validator(universe: Optional[Iterable[str]] = None) -> TickerValidator:
    """
    universe verilirse SADECE o set'i tarar. Verilmezse SEC master listini
    tarar (tum US ticker'lari).
    """
    global _validator
    if _validator is None:
        from config import settings
        path = settings.STATE_DIR / "ticker_cik.json"
        u = set(universe) if universe else None
        _validator = TickerValidator(path, universe=u)
    return _validator


def reset_validator() -> None:
    """Test/yeniden ayarlama icin singleton'i sifirlar."""
    global _validator
    _validator = None
