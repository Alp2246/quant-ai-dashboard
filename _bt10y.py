# -*- coding: utf-8 -*-
"""10 yillik backtest: core hisseler, guncel config (BACKTEST_LOOKBACK_YEARS=10)."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd

from config import CORE_TICKERS, HISTORY_PERIOD, BACKTEST_LOOKBACK_YEARS
from technical_indicators import add_indicators
from backtest import backtest_strategy

print(f"HISTORY_PERIOD={HISTORY_PERIOD}  LOOKBACK={BACKTEST_LOOKBACK_YEARS}y")
print(f"{'Hisse':<7}{'Islem':>6}{'Win%':>7}{'OrtGet%':>9}{'Bilesik%':>10}{'AL-TUT%':>9}{'Alpha':>8}{'Sharpe':>8}{'MaxDD%':>8}")
print("-" * 78)

agg = {"n": 0, "wins": 0, "ret_sum": 0.0, "cum": 1.0}
rows = []
for t in CORE_TICKERS:
    try:
        df = yf.Ticker(t).history(period=HISTORY_PERIOD, interval="1d", auto_adjust=True)
        if df is None or len(df) < 60:
            print(f"{t:<7} YETERSIZ VERI ({0 if df is None else len(df)} bar)")
            continue
        df = add_indicators(df)
        r = backtest_strategy(df, years=BACKTEST_LOOKBACK_YEARS)
        n = r["n_trades"]
        print(f"{t:<7}{n:>6}{r['win_rate']:>7}{r['avg_return']:>9}"
              f"{r['cum_return']:>10}{r['buy_hold_return']:>9}"
              f"{r['alpha_vs_bh']:>8}{r['sharpe_ratio']:>8}{r['max_drawdown_pct']:>8}")
        rows.append({"ticker": t, **{k: r[k] for k in
                      ("n_trades", "win_rate", "avg_return", "cum_return",
                       "buy_hold_return", "alpha_vs_bh", "sharpe_ratio",
                       "max_drawdown_pct", "exit_counts")}})
        agg["n"] += n
        agg["wins"] += round(n * r["win_rate"] / 100)
        agg["ret_sum"] += r["total_return"]
        agg["cum"] *= (1 + r["cum_return"] / 100)
    except Exception as e:
        print(f"{t:<7} HATA: {e}")

print("-" * 78)
if agg["n"]:
    print(f"TOPLAM islem={agg['n']}  win_rate=%{agg['wins']/agg['n']*100:.1f}  "
          f"bilesik portfoy getirisi=%{(agg['cum']-1)*100:+.1f}  "
          f"(her hisse esit sermaye, islem bilesik)")
import json
with open("_bt10y_results.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=2, ensure_ascii=False, default=str)
print("Detay: _bt10y_results.json")
