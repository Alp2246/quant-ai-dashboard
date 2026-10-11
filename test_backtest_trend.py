# -*- coding: utf-8 -*-
"""test_backtest_trend.py — v11.0 trend kurali regresyon testi.

11.10.2026 olcumlu vaka: eski salinim kurali islem basi -%0.22 beklenti
uretiyordu; kok neden ufuk uyusmazligiydi. Bu test yeni kuralin yapisal
ozelliklerini sabitler — delik geri acilirsa bagirir:
  1. Sinyal tabanli SAT uretilmez (cikis yapısaldir: SL/TP/TIME).
  2. Fiyat SMA200 altindayken AL uretilmez (rejim filtresi).
  3. Rejim ustunde RSI kesisimi AL uretir.
  4. Uretim backtest'i SAT cikisi icermez; TP bariyeri 6xATR.
"""
import inspect
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

from backtest import backtest_strategy, generate_signals
from technical_indicators import add_indicators

PASS = 0
FAIL = 0


def ok(ad, kosul, mesaj=""):
    global PASS, FAIL
    if kosul:
        PASS += 1
        print(f"OK  {ad}")
    else:
        FAIL += 1
        print(f"FAIL {ad}  {mesaj}")


# --- 1-3) Sinyal uretimi: dogrudan indikator enjekte et ---------------------
n = 120
idx = pd.date_range("2024-01-01", periods=n, freq="B")
df = pd.DataFrame({
    "Close": np.linspace(100, 140, n),
    "rsi": np.full(n, 55.0),
    "macd_hist": np.full(n, 0.5),
    "sma_200": np.linspace(90, 110, n),
}, index=idx)
df.iloc[9, df.columns.get_loc("rsi")] = 48.0   # 50 kesisim simulasyonu
df.iloc[10, df.columns.get_loc("rsi")] = 52.0

sig = generate_signals(df)
ok("sinyal serisinde SAT yok", set(sig.unique()) <= {"AL", "BEKLE"},
   f"bulunan: {set(sig.unique())}")

df_dip = df.copy()
df_dip["Close"] = 50.0                          # her yerde SMA200 alti
sig_dip = generate_signals(df_dip)
ok("SMA200 altinda AL uretilmez", (sig_dip == "AL").sum() == 0,
   f"AL sayisi={(sig_dip == 'AL').sum()}")

sig2 = generate_signals(df)
ok("rejim ustunde RSI kesisimi AL uretir", (sig2 == "AL").sum() == 1,
   f"AL sayisi={(sig2 == 'AL').sum()} (beklenen 1, index 10)")

# --- 4) Uretim backtest'i: dusus sonrasi duzenli dip + trend ----------------
gun = np.arange(600)
drift = np.where(gun < 150, -0.0015, 0.0022)
salinim = 0.013 * np.sin(gun / 9.0)             # RSI'yi 50 etrafinda gezdirir
fiyat = 100 * np.exp(np.cumsum(drift + salinim))
ohlc = pd.DataFrame({
    "Open": fiyat, "High": fiyat * 1.008, "Low": fiyat * 0.992, "Close": fiyat,
    "Volume": 1e6,
}, index=pd.date_range("2022-01-03", periods=600, freq="B"))
ohlc = add_indicators(ohlc)
r = backtest_strategy(ohlc, years=2.0)
nedenler = set(r["trades_df"]["exit_reason"]) if not r["trades_df"].empty else set()
ok("backtest cikislari SAT icermez",
   nedenler <= {"TP", "SL", "TIME", "END"},
   f"exit_reason'ler: {nedenler}")
ok("sentetik trendde islem uretilir", r["n_trades"] > 0,
   f"islem={r['n_trades']}")

# --- 5) TP carpani uretimde 6xATR (v11.0) ------------------------------------
tp_varsayilan = inspect.signature(backtest_strategy).parameters["atr_tp_mult"].default
ok("atr_tp_mult varsayilani 6.0", tp_varsayilan == 6.0, f"got={tp_varsayilan}")

print("-" * 60)
print(f"{PASS}/{PASS+FAIL} test gecti")
sys.exit(1 if FAIL else 0)
