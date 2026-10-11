# -*- coding: utf-8 -*-
"""DUZELTME VARYANTI — tezle uyumlu kurallar:
  Giris  : RSI 50 yukari kesisimi + fiyat SMA200 ustunde (yalniz yukselis rejiminde)
  Cikis  : SL 2xATR / TP 6xATR / TIME 60 gun / sinyal-satiri YOK
  (Murphy salinim kurali -> trend-takip kurali; ufuk 5 gun -> 60 gun)"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import yfinance as yf
import pandas as pd

import backtest as bt
from config import CORE_TICKERS, HISTORY_PERIOD, BACKTEST_LOOKBACK_YEARS
from technical_indicators import add_indicators


def generate_trend(df: pd.DataFrame, window: int = 5) -> pd.Series:
    rsi = df["rsi"]
    hist = df["macd_hist"]
    sma200 = df["sma_200"] if "sma_200" in df.columns else df["Close"].rolling(200).mean()

    rsi_cross_up = (rsi.shift(1) < 50) & (rsi >= 50)
    hist_ok = hist > 0
    regime = df["Close"] > sma200

    buy = rsi_cross_up & hist_ok & regime
    sell = pd.Series(False, index=df.index)   # yapısal cikis: yalniz SL/TP/TIME
    signals = pd.Series("BEKLE", index=df.index)
    signals[buy] = "AL"
    signals[sell] = "SAT"
    return signals


bt.generate_signals = generate_trend

print("DUZELTME VARYANTI: rejim+RSI50 giris, TP=6xATR, SL=2xATR, TIME=60gun, SAT yok")
print(f"{'Hisse':<7}{'Islem':>6}{'Win%':>7}{'OrtGet%':>9}{'Bilesik%':>10}{'AL-TUT%':>9}{'Alpha':>8}{'Sharpe':>8}{'MaxDD%':>8}")
print("-" * 78)
tot_n, tot_w, tot_ret, cum = 0, 0, 0.0, 1.0
for t in CORE_TICKERS:
    df = yf.Ticker(t).history(period=HISTORY_PERIOD, interval="1d", auto_adjust=True)
    if df is None or len(df) < 60:
        continue
    df = add_indicators(df)
    r = bt.backtest_strategy(df, years=BACKTEST_LOOKBACK_YEARS,
                             atr_tp_mult=6.0, holding_days=60)
    n = r["n_trades"]
    print(f"{t:<7}{n:>6}{r['win_rate']:>7}{r['avg_return']:>9}"
          f"{r['cum_return']:>10}{r['buy_hold_return']:>9}"
          f"{r['alpha_vs_bh']:>8}{r['sharpe_ratio']:>8}{r['max_drawdown_pct']:>8}")
    tot_n += n
    tot_w += round(n * r["win_rate"] / 100)
    tot_ret += r["total_return"]
    cum *= (1 + r["cum_return"] / 100)
print("-" * 78)
print(f"TOPLAM islem={tot_n}  win_rate=%{tot_w/tot_n*100:.1f}  "
      f"islem toplam=%{tot_ret:+.1f}  bilesik=%{(cum-1)*100:+.1f}")
