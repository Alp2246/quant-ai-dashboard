"""
correlation_matrix.py - Hisseler arasi korelasyon + Pair Trading firsati.

Pair Trading mantigi:
  - Tarihsel olarak yuksek korelasyonlu (>0.5) iki hisse
  - Son donemde fiyat orani z-score |z| > 2.0
  - Yukseleni SAT, geride kalani AL = arbitraj firsati
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def build_correlation(histories: dict[str, pd.DataFrame],
                      window_days: int = 60) -> pd.DataFrame:
    """
    Son window_days gunluk gunluk getiri korelasyon matrisi.
    histories: {ticker: df with 'Close'}
    """
    rets = {}
    for t, df in histories.items():
        if df is None or df.empty:
            continue
        close = df["Close"].pct_change().tail(window_days)
        rets[t] = close
    if not rets:
        return pd.DataFrame()

    aligned = pd.DataFrame(rets).dropna(how="all")
    if aligned.empty or len(aligned.columns) < 2:
        return pd.DataFrame()
    return aligned.corr()


def find_pair_opportunities(
    histories: dict[str, pd.DataFrame],
    min_corr: float = 0.50,
    zscore_threshold: float = 2.0,
    lookback_days: int = 90,
) -> list[dict]:
    """
    Pair trading firsatlari:
      1) (A, B) ciftinin son 90 gun korelasyonu >= min_corr
      2) A/B oraninin son 30 gun z-score'u |z| >= zscore_threshold

    Returns: liste of {pair, correlation, zscore, recommended_long,
                       recommended_short, ratio, ratio_mean, ratio_std}
    """
    # Tum hisselerin son N gun kapanis verisi
    closes = {}
    for t, df in histories.items():
        if df is None or df.empty:
            continue
        c = df["Close"].tail(lookback_days).copy()
        if len(c) >= 40:
            closes[t] = c
    if len(closes) < 2:
        return []

    aligned = pd.DataFrame(closes).dropna()
    if len(aligned) < 30:
        return []

    rets = aligned.pct_change().dropna()
    corr = rets.corr()
    tickers = list(aligned.columns)

    opportunities = []
    for i, a in enumerate(tickers):
        for b in tickers[i+1:]:
            c = corr.loc[a, b]
            if pd.isna(c) or abs(c) < min_corr:
                continue

            ratio = aligned[a] / aligned[b]
            if ratio.std() == 0 or len(ratio) < 30:
                continue
            mu = ratio.tail(30).mean()
            sigma = ratio.tail(30).std()
            if sigma == 0:
                continue
            z = (ratio.iloc[-1] - mu) / sigma

            if abs(z) >= zscore_threshold:
                # z > 0: A/B yuksek -> A oransal pahali, B ucuz
                if z > 0:
                    long_t, short_t = b, a
                else:
                    long_t, short_t = a, b

                opportunities.append({
                    "pair": f"{a} / {b}",
                    "ticker_a": a,
                    "ticker_b": b,
                    "correlation": round(float(c), 3),
                    "ratio": round(float(ratio.iloc[-1]), 4),
                    "ratio_mean_30d": round(float(mu), 4),
                    "ratio_std_30d": round(float(sigma), 4),
                    "zscore": round(float(z), 2),
                    "long":  long_t,
                    "short": short_t,
                    "signal_strength": min(100, abs(z) * 25),
                })

    opportunities.sort(key=lambda x: abs(x["zscore"]), reverse=True)
    return opportunities


def relative_performance(
    histories: dict[str, pd.DataFrame],
    lookback_days: int = 90,
) -> pd.DataFrame:
    """Son N gunde her hissenin getirisi (rakipler arasinda kim ne kadar?)."""
    rows = []
    for t, df in histories.items():
        if df is None or df.empty:
            continue
        c = df["Close"].tail(lookback_days)
        if len(c) < 5:
            continue
        start, end = float(c.iloc[0]), float(c.iloc[-1])
        ret = (end / start - 1) * 100 if start > 0 else 0
        rows.append({"ticker": t, "return_pct": round(ret, 2),
                      "start": start, "end": end})
    df_r = pd.DataFrame(rows).sort_values("return_pct", ascending=False)
    if not df_r.empty:
        df_r["rank"] = range(1, len(df_r) + 1)
    return df_r
