# -*- coding: utf-8 -*-
"""Kesin test: kural SECICI mi, yoksa rastgele girilse daha mi iyi?
Sinyal gunleri 5gun sonraki getiri vs ayni hissenin TUM gunleri 5gun sonraki getiri."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import yfinance as yf
import pandas as pd

from config import CORE_TICKERS, HISTORY_PERIOD, BACKTEST_LOOKBACK_YEARS
from technical_indicators import add_indicators
from backtest import generate_signals

HOLD = 5
sig_all, base_all = [], []
per_ticker = []

for t in CORE_TICKERS:
    df = yf.Ticker(t).history(period=HISTORY_PERIOD, interval="1d", auto_adjust=True)
    if df is None or len(df) < 60:
        continue
    df = add_indicators(df)
    cutoff = df.index[-1] - pd.Timedelta(days=int(BACKTEST_LOOKBACK_YEARS * 365.25))
    df = df[df.index >= cutoff]
    if len(df) < 30:
        continue
    sig = generate_signals(df)
    close = df["Close"]
    fwd = (close.shift(-HOLD) / close - 1) * 100   # her gun icin 5gun sonrasi

    sig_days = fwd[(sig == "AL").values]
    all_days = fwd.dropna()

    # Maliyetli hali (roundtrip 30bp, giris aninda kes)
    sig_net = sig_days - 0.30
    sig_all += list(sig_net.dropna())
    base_all += list(all_days)
    if len(sig_days.dropna()) >= 5:
        per_ticker.append((t, len(sig_days.dropna()),
                           sig_days.mean(), all_days.mean()))

print(f"5 GUN TUTMA KARSILASTIRMASI ({BACKTEST_LOOKBACK_YEARS:.0f}y pencere, maliyet: 30bp roundtrip)")
print("-" * 78)
print(f"{'Hisse':<7}{'SinyalGun':>10}{'Sinyal ort 5g':>15}{'Tum gun ort 5g':>16}{'Fark':>9}")
neg = 0
for t, n, s, b in per_ticker:
    fark = s - b
    neg += fark < 0
    print(f"{t:<7}{n:>10}{s:>15.2f}{b:>16.2f}{fark:>9.2f}")
print("-" * 78)
sa, ba = pd.Series(sig_all), pd.Series(base_all)
print(f"TOPLAM  sinyal gunu n={len(sa)}  ort=%{sa.mean():+.2f}  kazanma orani=%{(sa>0).mean()*100:.1f}")
print(f"        tum gun    n={len(ba)}  ort=%{ba.mean():+.2f}  kazanma orani=%{(ba>0).mean()*100:.1f}")
print(f"        kuralin sectigi gunler rastgele gunlerden %{sa.mean()-ba.mean():+.2f} kotu")
print(f"        {neg}/{len(per_ticker)} hisse kural rastgeleden kotu")
