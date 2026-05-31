"""
dca_calculator.py - Dollar-Cost-Averaging simulasyonu
Her ay sabit miktar yatirip 10 yil boyunca ne olurdu?
+ ML projeksiyonu ile ileri donuk 10y simulasyon.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from data_fetcher import fetch_history

logger = logging.getLogger(__name__)


def historical_dca(
    ticker: str,
    monthly_amount: float = 100.0,
    years: int = 10,
    df: pd.DataFrame | None = None,
) -> dict:
    """
    Gecmis veriyle DCA simulasyonu.
    Her ay basinda 'monthly_amount' $ ile hisseden satin al; bugune kadar tut.
    """
    try:
        if df is None or df.empty:
            df = fetch_history(ticker, period=f"{years}y")
    except Exception as e:
        logger.error("%s DCA fetch hatasi: %s", ticker, e)
        return _empty_dca(ticker, monthly_amount, years)

    if df is None or df.empty:
        return _empty_dca(ticker, monthly_amount, years)

    close = df["Close"].copy()
    close.index = pd.to_datetime(close.index).tz_localize(None) if close.index.tz else pd.to_datetime(close.index)

    # Ayin ilk gunundeki kapanis (ya da en yakin)
    monthly = close.resample("MS").first().dropna()
    cutoff = monthly.index[-1] - pd.DateOffset(years=years)
    monthly = monthly[monthly.index >= cutoff]
    if len(monthly) < 6:
        return _empty_dca(ticker, monthly_amount, years)

    rows = []
    shares = 0.0
    invested = 0.0
    for date, price in monthly.items():
        if price <= 0 or pd.isna(price):
            continue
        new_shares = monthly_amount / price
        shares += new_shares
        invested += monthly_amount
        value = shares * price
        rows.append({
            "date": date,
            "price": round(float(price), 2),
            "shares_bought": round(new_shares, 4),
            "total_shares": round(shares, 4),
            "invested": round(invested, 2),
            "value": round(value, 2),
            "return_pct": round((value / invested - 1) * 100, 2),
        })

    timeline = pd.DataFrame(rows)
    last_price = float(close.iloc[-1])
    final_value = shares * last_price
    profit = final_value - invested
    n_months = len(rows)
    n_years_real = n_months / 12

    irr_annual = 0.0
    if invested > 0 and n_years_real > 0:
        irr_annual = (final_value / invested) ** (1 / n_years_real) - 1

    return {
        "ticker": ticker,
        "monthly_amount": monthly_amount,
        "n_months": n_months,
        "years": round(n_years_real, 2),
        "invested": round(invested, 2),
        "final_value": round(final_value, 2),
        "profit": round(profit, 2),
        "return_pct": round((final_value / invested - 1) * 100, 1) if invested else 0,
        "irr_annual_pct": round(irr_annual * 100, 2),
        "total_shares": round(shares, 4),
        "last_price": round(last_price, 2),
        "timeline": timeline,
    }


def _empty_dca(ticker, monthly, years):
    return {
        "ticker": ticker, "monthly_amount": monthly,
        "n_months": 0, "years": years, "invested": 0,
        "final_value": 0, "profit": 0, "return_pct": 0,
        "irr_annual_pct": 0, "total_shares": 0, "last_price": 0,
        "timeline": pd.DataFrame(),
    }


def projected_dca(
    ticker: str,
    monthly_amount: float = 100.0,
    years_forward: int = 10,
    annual_growth_pct: float | None = None,
    df: pd.DataFrame | None = None,
) -> dict:
    """
    Ileri donuk DCA simulasyonu.
    Eger 'annual_growth_pct' verilmezse son 5 yillik CAGR otomatik hesaplanir.
    Volatiliteyi de hesaba kat: alt/ust bant olarak +/- std.
    """
    try:
        if df is None or df.empty:
            df = fetch_history(ticker, period="5y")
    except Exception as e:
        logger.error("%s proj-DCA fetch: %s", ticker, e)
        df = pd.DataFrame()

    if df is None or df.empty:
        return _empty_proj_dca(ticker, monthly_amount, years_forward)

    close = df["Close"].dropna()
    last = float(close.iloc[-1])

    # CAGR
    if annual_growth_pct is None:
        n = (close.index[-1] - close.index[0]).days / 365.25
        if n > 0 and float(close.iloc[0]) > 0:
            cagr = (last / float(close.iloc[0])) ** (1 / n) - 1
        else:
            cagr = 0.08
        # Asiri CAGR'leri kirp (10y projeksiyon icin gercekci)
        cagr = max(min(cagr, 0.40), -0.20)
    else:
        cagr = annual_growth_pct / 100

    # Volatilite -> +/-1 std bant
    monthly_ret = close.pct_change().resample("ME").apply(lambda x: (1 + x).prod() - 1).dropna()
    vol_annual = float(monthly_ret.std() * np.sqrt(12)) if len(monthly_ret) > 6 else 0.30

    monthly_rate_central = (1 + cagr) ** (1/12) - 1
    monthly_rate_up = (1 + cagr + vol_annual) ** (1/12) - 1
    monthly_rate_down = (1 + max(cagr - vol_annual, -0.5)) ** (1/12) - 1

    n_months = years_forward * 12
    price_central = last
    price_up = last
    price_down = last

    shares_c = shares_u = shares_d = 0.0
    invested = 0.0
    rows = []
    today = pd.Timestamp.today().normalize()

    for m in range(1, n_months + 1):
        price_central *= (1 + monthly_rate_central)
        price_up *= (1 + monthly_rate_up)
        price_down *= (1 + monthly_rate_down)
        price_down = max(price_down, 0.01)

        shares_c += monthly_amount / price_central
        shares_u += monthly_amount / price_up
        shares_d += monthly_amount / price_down
        invested += monthly_amount

        date = today + pd.DateOffset(months=m)
        rows.append({
            "date": date,
            "invested": round(invested, 2),
            "value_central": round(shares_c * price_central, 2),
            "value_up":      round(shares_u * price_up, 2),
            "value_down":    round(shares_d * price_down, 2),
            "price_central": round(price_central, 2),
        })

    timeline = pd.DataFrame(rows)
    fv_c = shares_c * price_central
    fv_u = shares_u * price_up
    fv_d = shares_d * price_down

    return {
        "ticker": ticker, "monthly_amount": monthly_amount,
        "years": years_forward, "n_months": n_months,
        "cagr_used_pct": round(cagr * 100, 2),
        "volatility_pct": round(vol_annual * 100, 1),
        "invested": round(invested, 2),
        "final_central": round(fv_c, 2),
        "final_up":      round(fv_u, 2),
        "final_down":    round(fv_d, 2),
        "multiple_central": round(fv_c / invested, 2) if invested else 0,
        "multiple_up":      round(fv_u / invested, 2) if invested else 0,
        "multiple_down":    round(fv_d / invested, 2) if invested else 0,
        "timeline": timeline,
    }


def _empty_proj_dca(ticker, monthly, years):
    return {
        "ticker": ticker, "monthly_amount": monthly, "years": years,
        "n_months": 0, "cagr_used_pct": 0, "volatility_pct": 0,
        "invested": 0, "final_central": 0, "final_up": 0, "final_down": 0,
        "multiple_central": 0, "multiple_up": 0, "multiple_down": 0,
        "timeline": pd.DataFrame(),
    }


def portfolio_dca(
    tickers: list[str],
    monthly_per_ticker: float = 100.0,
    years_back: int = 10,
    years_forward: int = 10,
) -> dict:
    """Tum hisseler icin gecmis + ileri DCA - toplam bakiye."""
    hist_results = {}
    proj_results = {}
    for t in tickers:
        try:
            hist_results[t] = historical_dca(t, monthly_per_ticker, years_back)
        except Exception as e:
            logger.error("%s historical_dca: %s", t, e)
            hist_results[t] = _empty_dca(t, monthly_per_ticker, years_back)
        try:
            proj_results[t] = projected_dca(t, monthly_per_ticker, years_forward)
        except Exception as e:
            logger.error("%s projected_dca: %s", t, e)
            proj_results[t] = _empty_proj_dca(t, monthly_per_ticker, years_forward)

    hist_total = sum(r["final_value"] for r in hist_results.values())
    hist_invested = sum(r["invested"] for r in hist_results.values())
    proj_total = sum(r["final_central"] for r in proj_results.values())
    proj_up = sum(r["final_up"] for r in proj_results.values())
    proj_down = sum(r["final_down"] for r in proj_results.values())
    proj_invested = sum(r["invested"] for r in proj_results.values())

    return {
        "historical": hist_results,
        "projected": proj_results,
        "historical_total_value": round(hist_total, 2),
        "historical_invested": round(hist_invested, 2),
        "historical_return_pct": round((hist_total / hist_invested - 1) * 100, 1) if hist_invested else 0,
        "projected_invested": round(proj_invested, 2),
        "projected_central_value": round(proj_total, 2),
        "projected_up_value": round(proj_up, 2),
        "projected_down_value": round(proj_down, 2),
    }
