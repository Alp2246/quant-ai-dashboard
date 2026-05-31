"""
fundamentals.py - Temel analiz: piyasa degeri, gelir buyumesi, nakit akisi
"""
from __future__ import annotations

import logging
from functools import lru_cache

import yfinance as yf

logger = logging.getLogger(__name__)


def _safe(val, default=0.0):
    try:
        if val is None:
            return default
        f = float(val)
        if f != f:  # NaN
            return default
        return f
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=64)
def get_fundamentals(ticker: str) -> dict:
    """yfinance temel veriler."""
    t = yf.Ticker(ticker)
    info = {}
    try:
        info = t.info or {}
    except Exception as e:
        logger.warning("%s info hatasi: %s", ticker, e)

    market_cap = _safe(info.get("marketCap"))
    revenue = _safe(info.get("totalRevenue"))
    revenue_growth = _safe(info.get("revenueGrowth")) * 100  # %
    profit_margin = _safe(info.get("profitMargins")) * 100   # %
    op_cashflow = _safe(info.get("operatingCashflow"))
    free_cashflow = _safe(info.get("freeCashflow"))
    debt_to_equity = _safe(info.get("debtToEquity"))
    pe_forward = _safe(info.get("forwardPE"))
    beta = _safe(info.get("beta"), 1.0)
    short_ratio = _safe(info.get("shortRatio"))
    target_mean = _safe(info.get("targetMeanPrice"))
    current_price = _safe(info.get("currentPrice"))

    upside_pct = 0.0
    if current_price > 0 and target_mean > 0:
        upside_pct = (target_mean / current_price - 1) * 100

    return {
        "ticker": ticker,
        "market_cap": market_cap,
        "market_cap_human": _human_money(market_cap),
        "revenue": revenue,
        "revenue_growth_pct": revenue_growth,
        "profit_margin_pct": profit_margin,
        "operating_cashflow": op_cashflow,
        "free_cashflow": free_cashflow,
        "debt_to_equity": debt_to_equity,
        "forward_pe": pe_forward,
        "beta": beta,
        "short_ratio": short_ratio,
        "target_mean_price": target_mean,
        "current_price": current_price,
        "analyst_upside_pct": upside_pct,
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
    }


def _human_money(v: float) -> str:
    if v >= 1e12:
        return f"${v/1e12:.2f}T"
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"


def fundamental_score(fund: dict) -> dict:
    """
    Temel analiz puani 0..100.
    Yuksek = saglam sirket. Bu ML feature olarak kullanilir.

    Bilesenler:
      - Gelir buyumesi (30 puan)
      - Karlilik       (20 puan)
      - Nakit akisi     (20 puan)
      - Analist hedef   (15 puan)
      - Borc oranı       (15 puan ters)
    """
    score = 0.0
    breakdown = {}

    # Gelir buyumesi: %0 -> 0, %30+ -> 30
    g = max(min(fund["revenue_growth_pct"], 50), -20)
    growth_pt = max(0, (g + 10) / 60 * 30)   # -10% -> 0, +50% -> 30
    breakdown["revenue_growth"] = round(growth_pt, 1)
    score += growth_pt

    # Karlilik (kar marji)
    pm = fund["profit_margin_pct"]
    if pm >= 20:
        prof_pt = 20
    elif pm >= 0:
        prof_pt = 10 + pm / 2
    elif pm >= -50:
        prof_pt = max(0, 10 + pm / 5)
    else:
        prof_pt = 0
    breakdown["profitability"] = round(prof_pt, 1)
    score += prof_pt

    # Nakit akisi (operating)
    if fund["operating_cashflow"] > 0:
        if fund["free_cashflow"] > 0:
            cf_pt = 20
        else:
            cf_pt = 12
    elif fund["operating_cashflow"] < 0:
        cf_pt = 5  # buyume sirketleri (kuantum vs.) genelde negatif
    else:
        cf_pt = 0
    breakdown["cashflow"] = round(cf_pt, 1)
    score += cf_pt

    # Analist hedef (upside)
    up = fund["analyst_upside_pct"]
    if up >= 30:
        ana_pt = 15
    elif up >= 0:
        ana_pt = 7 + up / 4
    elif up >= -20:
        ana_pt = max(0, 7 + up / 3)
    else:
        ana_pt = 0
    breakdown["analyst_target"] = round(ana_pt, 1)
    score += ana_pt

    # Borc / ozsermaye (dusuk iyi)
    d = fund["debt_to_equity"]
    if d <= 30:
        debt_pt = 15
    elif d <= 100:
        debt_pt = 15 - (d - 30) / 70 * 10
    elif d <= 200:
        debt_pt = 5 - (d - 100) / 100 * 5
    else:
        debt_pt = 0
    breakdown["balance_sheet"] = round(debt_pt, 1)
    score += debt_pt

    final = max(0, min(100, score))

    if final >= 70:
        rating = "GUCLU"
    elif final >= 50:
        rating = "ORTA"
    elif final >= 30:
        rating = "ZAYIF"
    else:
        rating = "RISKLI"

    return {
        "score": round(final, 1),
        "rating": rating,
        "breakdown": breakdown,
    }


def get_fundamental_summary(ticker: str) -> dict:
    """Tek fonksiyonda hem veriler hem skor."""
    fund = get_fundamentals(ticker)
    sc = fundamental_score(fund)
    return {**fund, **sc}
