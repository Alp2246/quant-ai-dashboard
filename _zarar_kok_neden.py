# -*- coding: utf-8 -*-
"""Neden zarardayiz — kok neden analizi.

Uretim kurali (RSI+MACD, TP=3xATR, SL=2xATR, TIME=20gun, RSI>65 sat)
uzerinden 10 hisse/10y: her islemin giris/cikis kaydiyla beylik
kutusu analizi. Zarari su bileşenlere ayirir:
  A) Beklenti (win rate x odul/risk orani)
  B) Cikis kurali katkisi (TP/SL/TIME/SAT bazinda)
  C) Zirve alimi (sinyal oncesi 20gun momentumu)
  D) Erken cikis (cikistan sonra 20/60gun kalan getiri)
  E) Islem maliyeti (30bp roundtrip)
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import yfinance as yf
import pandas as pd

from config import CORE_TICKERS, HISTORY_PERIOD, BACKTEST_LOOKBACK_YEARS
from technical_indicators import add_indicators
from backtest import backtest_strategy

all_trades = []
pre_sig = []      # zirve alimi olcumu
post_exit = []    # erken cikis olcumu
close_hist = {}

for t in CORE_TICKERS:
    df = yf.Ticker(t).history(period=HISTORY_PERIOD, interval="1d", auto_adjust=True)
    if df is None or len(df) < 60:
        continue
    df = add_indicators(df)
    close_hist[t] = df["Close"]
    r = backtest_strategy(df, years=BACKTEST_LOOKBACK_YEARS)
    for tr in r["trades"]:
        tr["ticker"] = t
        all_trades.append(tr)

tr = pd.DataFrame(all_trades)
n = len(tr)
rets = tr["return_pct"]

print("=" * 74)
print("A) BEKLENTI (Expectancy)")
print("=" * 74)
wins = rets[rets > 0]
loss = rets[rets <= 0]
print(f"islem={n}  win={len(wins)} (%{len(wins)/n*100:.1f})  kayip={len(loss)}")
print(f"ortalama KAZANAN islem : %+%{wins.mean():.2f}")
print(f"ortalama KAYBEDEN islem: %{loss.mean():.2f}")
print(f"odul/risk (payoff)     : {abs(wins.mean()/loss.mean()):.2f}")
print(f"islembasi beklenti     : %{rets.mean():+.3f}  ->  {n} islemde %{rets.sum():+.1f} toplam")
breakeven_wr = 1/(1+abs(wins.mean()/loss.mean()))*100
print(f"kira noktasi win rate  : %{breakeven_wr:.1f}  (gercek: %{len(wins)/n*100:.1f})")

print()
print("=" * 74)
print("B) CIKIS KURALI KATKISI")
print("=" * 74)
for reason in ("TP", "SL", "TIME", "SAT", "END"):
    sub = tr[tr["exit_reason"] == reason]
    if len(sub):
        print(f"{reason:<5} n={len(sub):>3} (%{len(sub)/n*100:>4.1f})  "
              f"ort=%{sub['return_pct'].mean():>+7.2f}  toplam katki=%{sub['return_pct'].sum():>+8.1f}  "
              f"ort.tutma={sub['days_held'].mean():.0f}gun")

print()
print("=" * 74)
print("C) ZIRVE ALIMI — sinyal oncesi 20 gun momentumu")
print("=" * 74)
moms = []
for _, row in tr.iterrows():
    s = close_hist[row["ticker"]]
    try:
        d = s.index.get_loc(pd.Timestamp(row["entry_date"]))
        if isinstance(d, slice): d = d.start
        if d >= 20:
            mom = (s.iloc[d] / s.iloc[d-20] - 1) * 100
            moms.append(mom)
    except Exception:
        pass
moms = pd.Series(moms)
print(f"sinyal aninda ortalama onceki-20gun getiri: %{'+%.1f' % moms.mean()}")
print(f"  (pozitifse kural RALLI SONRASI aliyor demektir)")
print(f"%25+ ralli sonrasi giris orani: %{(moms>25).mean()*100:.0f}")

print()
print("=" * 74)
print("D) ERKEN CIKIS — cikistan 20/60 gun SONRA kalan getiri")
print("=" * 74)
left20, left60 = [], []
for _, row in tr.iterrows():
    s = close_hist[row["ticker"]]
    try:
        d = s.index.get_loc(pd.Timestamp(row["exit_date"]))
        if isinstance(d, slice): d = d.start
        ex = s.iloc[d]
        if d+20 < len(s): left20.append((s.iloc[d+20]/ex-1)*100)
        if d+60 < len(s): left60.append((s.iloc[d+60]/ex-1)*100)
    except Exception:
        pass
l20, l60 = pd.Series(left20), pd.Series(left60)
print(f"cikistan 20gun sonra ort. kalan: %{l20.mean():+.2f} (n={len(l20)})")
print(f"cikistan 60gun sonra ort. kalan: %{l60.mean():+.2f} (n={len(l60)})")
print("  (pozitifse cikis kurali erken kesiyor demektir)")

print()
print("=" * 74)
print("E) ISLEM MALIYETI")
print("=" * 74)
rt_cost = 30  # bps roundtrip (10 komisyon + 5 slippage, iki yon)
print(f"{n} islem x ~%{rt_cost/100:.2f} roundtrip ≈ %{n*0.003:.1f} toplam surtunme")

tr.to_csv("_zarar_analiz_trades.csv", index=False)
print("\nKayit: _zarar_analiz_trades.json/.csv")
with open("_zarar_analiz_trades.json", "w", encoding="utf-8") as f:
    json.dump(all_trades, f, ensure_ascii=False, default=str)
