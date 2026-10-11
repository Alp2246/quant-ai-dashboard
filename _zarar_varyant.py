# -*- coding: utf-8 -*-
"""Karsilastirma: SAT kurali devre disi (yalniz SL/TP/TIME cikislari).
Eger zararin kaynagi cikis kuraliysa bu varyant duzelmeli."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd

import backtest as bt
from config import CORE_TICKERS, HISTORY_PERIOD, BACKTEST_LOOKBACK_YEARS
from technical_indicators import add_indicators

_orig = bt.generate_signals


def generate_no_sat(df: pd.DataFrame, window: int = 5) -> pd.Series:
    sig = _orig(df, window)
    # Sinyal cikisini kapat: SL/TP/TIME/END hala calisir
    sig = sig.replace("SAT", "BEKLE")
    return sig


bt.generate_signals = generate_no_sat

print("SAT'sIZ VARYANT (yalniz SL/TP/TIME cikisi):")
print(f"{'Hisse':<7}{'Islem':>6}{'Win%':>7}{'OrtGet%':>9}{'Bilesik%':>10}{'AL-TUT%':>9}{'Alpha':>8}{'Sharpe':>8}{'MaxDD%':>8}")
print("-" * 78)
tot_n, tot_w, tot_ret = 0, 0, 0.0
for t in CORE_TICKERS:
    df = yf.Ticker(t).history(period=HISTORY_PERIOD, interval="1d", auto_adjust=True)
    if df is None or len(df) < 60:
        continue
    df = add_indicators(df)
    r = bt.backtest_strategy(df, years=BACKTEST_LOOKBACK_YEARS)
    n = r["n_trades"]
    print(f"{t:<7}{n:>6}{r['win_rate']:>7}{r['avg_return']:>9}"
          f"{r['cum_return']:>10}{r['buy_hold_return']:>9}"
          f"{r['alpha_vs_bh']:>8}{r['sharpe_ratio']:>8}{r['max_drawdown_pct']:>8}")
    print(f"       cikis: {r['exit_counts']}")
    tot_n += n
    tot_w += round(n * r["win_rate"] / 100)
    tot_ret += r["total_return"]
print("-" * 78)
print(f"TOPLAM islem={tot_n}  win_rate=%{tot_w/tot_n*100:.1f}  islem toplam getiri=%{tot_ret:+.1f}")
