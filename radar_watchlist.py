"""
radar_watchlist.py - Manuel ekleneyen hisseler icin CAGR + Durability Score
"""
from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np
import pandas as pd
import yfinance as yf

from data_fetcher import fetch_history
from fundamentals import get_fundamentals

logger = logging.getLogger(__name__)


def compute_cagr(df: pd.DataFrame, years: int | None = None) -> dict:
    """
    Bilesik Yillik Buyume Orani (CAGR).
    years=None: tum mevcut donem; aksi halde son N yil.
    """
    if df is None or df.empty:
        return {"cagr_pct": 0, "years": 0, "start_price": 0, "end_price": 0}

    close = df["Close"].dropna()
    if years:
        cutoff = close.index[-1] - pd.DateOffset(years=years)
        close = close[close.index >= cutoff]
    if len(close) < 60:
        return {"cagr_pct": 0, "years": 0, "start_price": 0, "end_price": 0}

    start = float(close.iloc[0])
    end = float(close.iloc[-1])
    n_years = (close.index[-1] - close.index[0]).days / 365.25
    if n_years <= 0 or start <= 0:
        return {"cagr_pct": 0, "years": n_years, "start_price": start, "end_price": end}

    cagr = (end / start) ** (1 / n_years) - 1
    return {
        "cagr_pct": round(cagr * 100, 2),
        "years": round(n_years, 2),
        "start_price": round(start, 2),
        "end_price": round(end, 2),
        "total_return_pct": round((end / start - 1) * 100, 1),
    }


def _safe(v, default=0.0):
    try:
        if v is None: return default
        f = float(v)
        if f != f: return default
        return f
    except (TypeError, ValueError):
        return default


def durability_score(ticker: str, fund: dict | None = None) -> dict:
    """
    10 yil tutmaya uygunluk - 'Durability Score' 0..100
    6 boyut:
      1) Bilanco (Debt/Equity, Current Ratio)              18 pt
      2) Gelir kalitesi (Revenue Growth, Profit Margin)    18 pt
      3) Nakit ureticilik (FCF margin, Op CF)              18 pt
      4) Surdurulebilirlik (Beta, Insider/Inst sahiplik)   16 pt
      5) Buyume korunumu (Forward growth, Analyst upside)  16 pt
      6) Tekno gucu (R&D intensity, Gross Margin -> proxy for moat)  14 pt
    """
    if fund is None:
        try:
            fund = get_fundamentals(ticker)
        except Exception:
            fund = {}

    t = yf.Ticker(ticker)
    info = {}
    try:
        info = t.info or {}
    except Exception as e:
        logger.warning("%s info: %s", ticker, e)

    # ---- 1) Bilanco (18 pt) ----
    d_eq = _safe(info.get("debtToEquity"))
    curr_ratio = _safe(info.get("currentRatio"), 1.0)
    if d_eq <= 30:
        de_pt = 11
    elif d_eq <= 80:
        de_pt = 11 - (d_eq - 30) / 50 * 5
    elif d_eq <= 200:
        de_pt = 6 - (d_eq - 80) / 120 * 6
    else:
        de_pt = 0
    cr_pt = min(7, max(0, curr_ratio / 2.0 * 7))
    balance_pt = round(de_pt + cr_pt, 1)

    # ---- 2) Gelir kalitesi (18 pt) ----
    rev_growth = _safe(info.get("revenueGrowth")) * 100
    pm = _safe(info.get("profitMargins")) * 100
    rg_pt = min(9, max(0, (rev_growth + 10) / 40 * 9))
    pm_pt = min(9, max(0, (pm + 30) / 60 * 9))
    revenue_pt = round(rg_pt + pm_pt, 1)

    # ---- 3) Nakit (18 pt) ----
    op_cf = _safe(info.get("operatingCashflow"))
    fcf = _safe(info.get("freeCashflow"))
    rev = _safe(info.get("totalRevenue"))
    fcf_margin = (fcf / rev * 100) if rev > 0 else 0
    if op_cf > 0:
        cf_base = 9
    elif op_cf < 0 and fcf < 0:
        cf_base = 2
    else:
        cf_base = 5
    fcf_pt = min(9, max(0, (fcf_margin + 10) / 30 * 9))
    cash_pt = round(cf_base + fcf_pt, 1)

    # ---- 4) Surdurulebilirlik (16 pt) ----
    beta = _safe(info.get("beta"), 1.0)
    inst_own = _safe(info.get("heldPercentInstitutions")) * 100
    insider = _safe(info.get("heldPercentInsiders")) * 100
    if beta < 1.2:
        beta_pt = 8
    elif beta < 2:
        beta_pt = 8 - (beta - 1.2) * 6
    else:
        beta_pt = max(0, 3 - (beta - 2) * 1.5)
    own_pt = min(8, max(0, inst_own / 80 * 6 + insider / 30 * 2))
    sust_pt = round(beta_pt + own_pt, 1)

    # ---- 5) Buyume korunumu (16 pt) ----
    target = _safe(info.get("targetMeanPrice"))
    current = _safe(info.get("currentPrice"))
    upside = ((target / current - 1) * 100) if (current > 0 and target > 0) else 0
    fwd_growth = _safe(info.get("earningsQuarterlyGrowth")) * 100
    up_pt = min(10, max(0, (upside + 10) / 50 * 10))
    fwd_pt = min(6, max(0, (fwd_growth + 20) / 60 * 6))
    growth_pt = round(up_pt + fwd_pt, 1)

    # ---- 6) Tekno gucu - patent / R&D proxy (14 pt) ----
    # R&D intensity: yfinance dogrudan vermez; financials'tan cıkarmaya calis
    # Fallback: gross margin + esikleri (yuksek margin = teknolojik moat)
    gross_margin = _safe(info.get("grossMargins")) * 100  # %
    rd_intensity = 0.0
    try:
        fin = t.financials  # IS, son 4 yil
        if isinstance(fin, pd.DataFrame) and not fin.empty:
            # 'Research Development' satiri varsa
            for key in ("Research Development", "Research And Development"):
                if key in fin.index:
                    rd = _safe(fin.loc[key].iloc[0])
                    revenue = _safe(info.get("totalRevenue"))
                    if revenue > 0:
                        rd_intensity = rd / revenue * 100
                    break
    except Exception:
        pass

    # Patent kalite proxisi: gross margin > %40 -> tekno moat var
    if gross_margin >= 60:
        gm_pt = 7
    elif gross_margin >= 40:
        gm_pt = 5 + (gross_margin - 40) / 20 * 2
    elif gross_margin >= 20:
        gm_pt = 2 + (gross_margin - 20) / 20 * 3
    elif gross_margin > 0:
        gm_pt = gross_margin / 20 * 2
    else:
        gm_pt = 0

    # R&D %: 15+ = mukemmel (ASML, Intel %15+); 5-15 normal
    if rd_intensity >= 15:
        rd_pt = 7
    elif rd_intensity >= 5:
        rd_pt = 3 + (rd_intensity - 5) / 10 * 4
    elif rd_intensity > 0:
        rd_pt = rd_intensity / 5 * 3
    else:
        rd_pt = 0

    tech_pt = round(gm_pt + rd_pt, 1)

    total = round(balance_pt + revenue_pt + cash_pt + sust_pt + growth_pt + tech_pt, 1)

    if total >= 75:
        rating = "10y TUT - SAGLAM"
        verdict = "Uzun vadeye uygun: bilanco saglikli, nakit uretiyor"
    elif total >= 55:
        rating = "10y TUT - ORTA"
        verdict = "Tutulabilir ama izlenmeli"
    elif total >= 35:
        rating = "RISKLI"
        verdict = "Uzun vade icin riskli: zayif noktalar var"
    else:
        rating = "SPEKULATIF"
        verdict = "Cok spekulatif: kuvvetli volatilite, zayif finansal"

    return {
        "ticker": ticker,
        "durability": total,
        "rating": rating,
        "verdict": verdict,
        "breakdown": {
            "balance_sheet": balance_pt,
            "revenue_quality": revenue_pt,
            "cash_generation": cash_pt,
            "sustainability": sust_pt,
            "growth_potential": growth_pt,
            "tech_moat": tech_pt,
        },
        "raw": {
            "debt_to_equity": d_eq,
            "current_ratio": curr_ratio,
            "revenue_growth_pct": rev_growth,
            "profit_margin_pct": pm,
            "fcf_margin_pct": round(fcf_margin, 2),
            "gross_margin_pct": round(gross_margin, 2),
            "rd_intensity_pct": round(rd_intensity, 2),
            "beta": beta,
            "inst_ownership_pct": inst_own,
            "insider_ownership_pct": insider,
            "analyst_upside_pct": round(upside, 1),
            "earnings_growth_pct": fwd_growth,
        },
    }


def watchlist_analyze(ticker: str) -> dict:
    """
    Tam watchlist analizi: fiyat gecmisi (10y), CAGR'lar, fundamental, durability.
    """
    try:
        df = fetch_history(ticker, period="10y")
    except Exception as e:
        logger.error("%s fiyat hatasi: %s", ticker, e)
        df = pd.DataFrame()

    try:
        fund = get_fundamentals(ticker)
    except Exception as e:
        logger.error("%s fundamental hatasi: %s", ticker, e)
        fund = {}

    try:
        durab = durability_score(ticker, fund)
    except Exception as e:
        logger.error("%s durability hatasi: %s", ticker, e)
        durab = {"durability": 0, "rating": "VERI YOK", "verdict": str(e),
                 "breakdown": {}, "raw": {}}

    cagr_10y = compute_cagr(df, years=10)
    cagr_5y = compute_cagr(df, years=5)
    cagr_1y = compute_cagr(df, years=1)

    # 10y projeksiyon (basit): son 5y CAGR'i 10 yil ekstrapole et
    proj_growth = cagr_5y["cagr_pct"]
    last_price = cagr_5y["end_price"] or 0
    projected_10y = round(last_price * (1 + proj_growth / 100) ** 10, 2) if last_price else 0
    if last_price > 0:
        projected_multiple = round(projected_10y / last_price, 1)
    else:
        projected_multiple = 0

    return {
        "ticker": ticker,
        "df": df,
        "fundamental": fund,
        "durability": durab,
        "cagr_10y": cagr_10y,
        "cagr_5y": cagr_5y,
        "cagr_1y": cagr_1y,
        "last_price": last_price,
        "projected_10y": projected_10y,
        "projected_multiple_10y": projected_multiple,
    }
