"""
risk_distribution.py - 10 yillik vadede portfoy risk dagilim haritasi
'Bust' (batma) vs '10x'/'100x' (asiri yukseliş) ihtimallerinin görselleştirmesi.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def classify_outcome(
    durability: float,
    master_score: float,
    fund_score: float,
    cagr_5y: float,
    volatility_annual: float,
) -> dict:
    """
    Sezgisel (heuristic) sinif tahmini:
      P(bust)  - 10y'da -%80'den fazla degerini kaybetme ihtimali
      P(10x)   - 10y'da 10 katina cikma ihtimali
      P(100x)  - 10y'da 100 katina cikma ihtimali (ultra spekulatif)
      P(stable)= 1 - (bust + 10x + 100x)
    """
    # Durability dusukse bust riski yuksek
    bust = max(0.02, 0.55 - durability / 100 * 0.50)

    # CAGR yuksek + dusuk durability = 100x potansiyel
    if cagr_5y > 50:
        cagr_factor = 0.20
    elif cagr_5y > 25:
        cagr_factor = 0.10
    elif cagr_5y > 10:
        cagr_factor = 0.05
    else:
        cagr_factor = 0.01
    vol_factor = min(0.20, volatility_annual / 200)
    x100 = max(0.0, min(0.25, cagr_factor + vol_factor * 0.4 - durability / 100 * 0.05))

    # 10x potansiyel
    if cagr_5y > 25:
        x10 = 0.30 + min(0.30, master_score / 100 * 0.30)
    elif cagr_5y > 10:
        x10 = 0.15 + master_score / 100 * 0.20
    else:
        x10 = 0.05 + master_score / 100 * 0.15

    # Normalize - toplam <=1
    total = bust + x10 + x100
    if total > 0.92:
        scale = 0.92 / total
        bust *= scale
        x10 *= scale
        x100 *= scale
    stable = max(0.0, 1.0 - (bust + x10 + x100))

    risk_band = "DUSUK" if durability >= 70 else ("ORTA" if durability >= 50 else ("YUKSEK" if durability >= 30 else "SPEKULATIF"))

    return {
        "p_bust":   round(bust * 100, 1),
        "p_stable": round(stable * 100, 1),
        "p_10x":    round(x10 * 100, 1),
        "p_100x":   round(x100 * 100, 1),
        "risk_band": risk_band,
    }


def build_distribution(results: dict) -> pd.DataFrame:
    """
    results: {ticker: analyze_ticker(...) cikti + durability eklenmis}
    """
    rows = []
    for t, r in results.items():
        tech = r["technical"]
        fund = r["fundamental"]
        master = r["master"]
        # CAGR/volatilite (df'den)
        df = r["df"]
        close = df["Close"].dropna()
        cagr_5y = 0
        vol = 0
        if len(close) > 60:
            n = (close.index[-1] - close.index[0]).days / 365.25
            if n > 0 and float(close.iloc[0]) > 0:
                cagr_5y = ((float(close.iloc[-1]) / float(close.iloc[0])) ** (1 / max(n, 0.5)) - 1) * 100
            vol = float(close.pct_change().std() * (252 ** 0.5) * 100)
        durab = r.get("durability_score") or 50
        if isinstance(durab, dict):
            durab = durab.get("durability", 50)

        bucket = classify_outcome(durab, master["master_score"], fund.get("score", 50), cagr_5y, vol)
        rows.append({
            "ticker": t,
            "durability": durab,
            "master_score": master["master_score"],
            "cagr_5y_pct": round(cagr_5y, 1),
            "volatility_pct": round(vol, 1),
            **bucket,
        })
    return pd.DataFrame(rows)
