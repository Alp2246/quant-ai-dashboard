"""
data_fetcher.py - yfinance ile fiyat ve haber verisi
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf

from config import CURRENCY_HINTS, FX_TO_USD, HISTORY_INTERVAL, HISTORY_PERIOD, TICKERS
from technical_indicators import add_indicators

logger = logging.getLogger(__name__)


def fetch_history(ticker: str, period: str = HISTORY_PERIOD,
                  retries: int = 2) -> pd.DataFrame:
    """
    Gecmis OHLCV + teknik indikatorler. Yabanci borsalar (HK, Shanghai) icin
    yfinance hata verirse tekrar dene.
    """
    last_err = None
    for attempt in range(retries + 1):
        try:
            t = yf.Ticker(ticker)
            df = t.history(period=period, interval=HISTORY_INTERVAL,
                           auto_adjust=True)
            if df.empty:
                raise ValueError(f"{ticker} icin veri yok (deneme {attempt+1})")
            df.index = pd.to_datetime(df.index)
            # Tek satir kalirsa indikatör NaN; en az 30 gun olsun
            if len(df) < 30:
                raise ValueError(f"{ticker} yetersiz veri: {len(df)} gun")
            return add_indicators(df)
        except Exception as e:
            last_err = e
            logger.warning("%s deneme %d basarisiz: %s", ticker, attempt+1, e)
            if attempt < retries:
                continue
    raise ValueError(f"{ticker} icin veri alinamadi: {last_err}")


def get_currency(ticker: str) -> str:
    """yfinance'den para birimi, yoksa CURRENCY_HINTS fallback."""
    try:
        info = yf.Ticker(ticker).fast_info
        curr = getattr(info, "currency", None)
        if curr:
            return curr
    except Exception:
        pass
    return CURRENCY_HINTS.get(ticker, "USD")


def to_usd(price: float, currency: str) -> float:
    """Para birimini USD'ye cevir (yaklasik)."""
    rate = FX_TO_USD.get(currency, 1.0)
    return price * rate


def fetch_all_histories(tickers: Optional[list[str]] = None) -> dict[str, pd.DataFrame]:
    tickers = tickers or TICKERS
    result = {}
    for sym in tickers:
        try:
            result[sym] = fetch_history(sym)
            logger.info("%s: %d gun veri", sym, len(result[sym]))
        except Exception as e:
            logger.warning("%s veri hatasi: %s", sym, e)
    return result


def fetch_yfinance_news(ticker: str, limit: int = 10) -> list[dict]:
    """yfinance uzerinden haber basliklari."""
    try:
        t = yf.Ticker(ticker)
        news = t.news or []
        items = []
        for n in news[:limit]:
            content = n.get("content", n)
            title = content.get("title", n.get("title", ""))
            summary = content.get("summary", n.get("summary", ""))
            pub = content.get("pubDate", n.get("providerPublishTime", ""))
            items.append({
                "title": title or "",
                "summary": summary or "",
                "published": pub,
                "source": "yfinance",
            })
        return items
    except Exception as e:
        logger.warning("%s haber hatasi: %s", ticker, e)
        return []


def yearly_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Yil bazinda getiri %."""
    close = df["Close"]
    yearly = close.resample("YE").last().pct_change() * 100
    out = pd.DataFrame({
        "year": yearly.index.year,
        "return_pct": yearly.values,
    }).dropna()
    return out


def current_quote(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.fast_info
    return {
        "price": getattr(info, "last_price", None) or getattr(info, "lastPrice", None),
        "currency": getattr(info, "currency", "USD"),
        "market_cap": getattr(info, "market_cap", None),
        "updated": datetime.now().isoformat(timespec="seconds"),
    }
