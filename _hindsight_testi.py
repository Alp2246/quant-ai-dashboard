# -*- coding: utf-8 -*-
"""Madde 3: Mayis zirvesi hindsight'inin tersi - tabloyu SINYAL TARIHLERINDEN kurar.
Aynı $1000/hisse sabit portfoyu, alis fiyati = sinyal gunu kapanis.
Karsilastirma: SMH ve SOXX ayni pencereler, ayni tarihlerden itibaren.
"""
import json
import yfinance as yf

SINYALLER = {
    "IONQ": "2026-05-26",
    "RGTI": "2026-05-26",
    "LAES": "2026-05-26",
    "QBTS": "2026-05-27",
    "ATOM": "2026-05-27",
    "NVTS": "2026-06-05",
    "POET": "2026-07-31",
    "AXTI": "2026-08-03",
}
SEMIS = list(SINYALLER) + ["SMH", "SOXX"]
SEMbol = sorted(set(SEMIS))

hist = {}
for t in SEMbol:
    df = yf.download(t, start="2026-05-20", progress=False, auto_adjust=True)
    if df is None or df.empty:
        print(f"UYARI: {t} verisi yok")
        continue
    s = df["Close"]
    if isinstance(s, __import__("pandas").DataFrame):
        s = s.iloc[:, 0]
    hist[t] = s

def kapanis(t, tarih):
    s = hist[t]
    s = s[s.index.strftime("%Y-%m-%d") <= tarih]
    return float(s.iloc[-1])

son_tarih = max(s.index.strftime("%Y-%m-%d").max() for s in hist.values())
son_kapanis = {t: float(hist[t].iloc[-1]) for t in hist}

toplam_ilk = 0.0
toplam_son = 0.0
smh_toplam_ilk = 0.0
smh_toplam_son = 0.0
soxx_toplam_ilk = 0.0
soxx_toplam_son = 0.0
print(f"\nSon kapanis tarihi: {son_tarih}")
print(f"{'Hisse':<6} {'Sinyal':<12} {'Alis':>9} {'Son':>9} {'Getiri%':>9} {'SMH%':>8} {'SOXX%':>8}")
for t, starih in sorted(SINYALLER.items(), key=lambda kv: kv[1]):
    alis = kapanis(t, starih)
    son = son_kapanis[t]
    getiri = (son / alis - 1) * 100
    smh_alis = kapanis("SMH", starih)
    smh_getiri = (son_kapanis["SMH"] / smh_alis - 1) * 100
    soxx_alis = kapanis("SOXX", starih)
    soxx_getiri = (son_kapanis["SOXX"] / soxx_alis - 1) * 100
    toplam_ilk += 1000.0
    toplam_son += 1000.0 * (son / alis)
    smh_toplam_ilk += 1000.0
    smh_toplam_son += 1000.0 * (son_kapanis["SMH"] / smh_alis)
    soxx_toplam_ilk += 1000.0
    soxx_toplam_son += 1000.0 * (son_kapanis["SOXX"] / soxx_alis)
    print(f"{t:<6} {starih:<12} {alis:>9.2f} {son:>9.2f} {getiri:>9.1f} {smh_getiri:>8.1f} {soxx_getiri:>8.1f}")

print(f"\nPortfoy $8000 sinyal-tarihli: ${toplam_son:,.0f} ({(toplam_son/toplam_ilk-1)*100:+.1f}%)")
print(f"Ayni dolar SMH'ye koysaydin : ${smh_toplam_son:,.0f} ({(smh_toplam_son/smh_toplam_ilk-1)*100:+.1f}%)")
print(f"Ayni dolar SOXX'e koysaydin: ${soxx_toplam_son:,.0f} ({(soxx_toplam_son/soxx_toplam_ilk-1)*100:+.1f}%)")
