# -*- coding: utf-8 -*-
"""alerts.log'daki ilk GÜÇLÜ AL sinyallerini geriye dönük test eder.
Her hisseye sinyal aninda $1000 yatirildigini varsayar, bugune kadar getiriyi hesaplar.
"""
import yfinance as yf
import pandas as pd

SIGNALS = {
    "IONQ": "2026-05-26",
    "RGTI": "2026-05-26",
    "LAES": "2026-05-26",
    "QBTS": "2026-05-27",
    "ATOM": "2026-05-27",
    "NVTS": "2026-06-05",
    "POET": "2026-07-31",
    "AXTI": "2026-08-03",
}
PER_TICKER = 1000.0

rows = []
total_inv = 0.0
total_val = 0.0

for t, d in SIGNALS.items():
    h = yf.Ticker(t).history(start=d, auto_adjust=True)
    if h.empty:
        print(f"{t}: VERI YOK")
        continue
    # sinyal gunu kapanis (sinyal saatleri cogu kapanis sonrasi)
    px_buy = float(h["Close"].iloc[0])
    px_now = float(h["Close"].iloc[-1])
    buy_date = h.index[0].date()
    last_date = h.index[-1].date()
    shares = PER_TICKER / px_buy
    val = shares * px_now
    pnl = val - PER_TICKER
    pct = pnl / PER_TICKER * 100
    total_inv += PER_TICKER
    total_val += val
    rows.append((t, str(buy_date), px_buy, px_now, pct, pnl, str(last_date)))

print(f"{'Hisse':<6} {'Alis':<11} {'Alis$':>8} {'Simdi$':>8} {'Getiri%':>9} {'K/Z$':>10}")
for r in rows:
    print(f"{r[0]:<6} {r[1]:<11} {r[2]:>8.2f} {r[3]:>8.2f} {r[4]:>9.1f} {r[5]:>10.2f}")
print("-" * 55)
tp = total_val - total_inv
print(f"TOPLAM yatirim: ${total_inv:,.0f}  deger: ${total_val:,.0f}  K/Z: ${tp:+,.2f} (%{tp/total_inv*100:+.1f})")

# SPY kiyaslamasi (ayni donem, esit agirlikli)
spy = yf.Ticker("SPY").history(start="2026-05-26", auto_adjust=True)
spy_ret = float(spy["Close"].iloc[-1]) / float(spy["Close"].iloc[0]) - 1
print(f"SPY ayni donem: %{spy_ret*100:+.1f}")
print("Veri son tarihi:", rows[0][6])
