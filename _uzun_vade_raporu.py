# -*- coding: utf-8 -*-
"""Ocak 2026 girisi icin uzun vade (2030/2035/2040) aday raporu uretir.
Kaynak: taze master_scores.json (kapili skor) + sector_tam bantlari +
moonshot_detector + guncel fiyat. Dosyaya yazar: UZUN_VADE_RAPORU.md"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf

from sector_tam import (SECTOR_TAM_CAGR_PCT, get_sector,
                        get_ticker_max_cagr_10y, get_ticker_price_cap_10y)
from moonshot_detector import detect_moonshot, get_explosive_factor
from strategic_overlays import SPECULATIVE_TICKERS

scores = json.load(open("alpha_engine/data/state/master_scores.json",
                         encoding="utf-8"))["tickers"]

rows = []
for t, r in scores.items():
    if r.get("error"):
        continue
    sec = get_sector(t)
    band = SECTOR_TAM_CAGR_PCT.get(sec, 10.0)
    cap_cagr = get_ticker_max_cagr_10y(t)
    cap_px = get_ticker_price_cap_10y(t)
    try:
        ms = detect_moonshot(t)
    except Exception:
        ms = {}
    try:
        px = float(yf.Ticker(t).history(period="5d", auto_adjust=True)["Close"].iloc[-1])
    except Exception:
        px = None
    g = r.get("gates") or {}
    rows.append({
        "ticker": t, "sec": sec, "band": band, "cap_cagr": cap_cagr,
        "cap_px": cap_px, "px": px,
        "raw": r.get("score_raw"), "final": r.get("master_score"),
        "verdict": r.get("verdict"),
        "M_market": g.get("M_market"), "M_overfit": g.get("M_overfit"),
        "M_fund": g.get("M_fund"),
        "reasons": "; ".join((g.get("reasons") or [])[:2]),
        "jcurve": ms.get("j_curve_score"), "moon_verdict": ms.get("verdict"),
        "explosive": get_explosive_factor(t),
        "spec": t in SPECULATIVE_TICKERS,
    })

rows.sort(key=lambda x: -(x["raw"] or 0))
L = []
A = L.append
A("# UZUN VADE ADAY RAPORU — Ocak 2026 girisi, 2030/2035/2040 ufku")
A("")
A(f"_Skorlar: {scores and 'taze'} (gunluk islem {scores.get('WOLF',{}).get('updated_at','?')[:10]}). "
  "Bu rapor yatirim tavsiyesi degildir; sistem ciktisinin ozetidir._")
A("")
A("## Kapili skor tablosu (ham skor siralı)")
A("")
A("| Hisse | Sektor | Fiyat | Ham | Final | Verdict | Mkt/Ovf/Fnd | J-Curve |")
A("|---|---|---|---|---|---|---|---|")
for r in rows:
    A(f"| {r['ticker']} | {r['sec']} | {('%.2f' % r['px']) if r['px'] else '?'} "
      f"| {r['raw']} | {r['final']} | {r['verdict']} "
      f"| {r['M_market']}/{r['M_overfit']}/{r['M_fund']} | {r['jcurve']} |")
A("")
A("## 10y bant ve tavanlar (sector_tam)")
A("")
A("| Hisse | Sektor CAGR bandı | Hisse CAGR tavanı | 10y fiyat tavanı | Patlama faktörü |")
A("|---|---|---|---|---|")
for r in rows:
    A(f"| {r['ticker']} | ~%{r['band']:.0f} | "
      f"{('%%%.0f' % r['cap_cagr']) if r['cap_cagr'] else '—'} | "
      f"{('$%.0f' % r['cap_px']) if r['cap_px'] else '—'} | {r['explosive']} |")
A("")
A("## Gate gerekçeleri (neden şu an AL yok)")
A("")
for r in rows:
    if r["reasons"]:
        A(f"- **{r['ticker']}**: {r['reasons']}")
A("")
open("UZUN_VADE_RAPORU.md", "w", encoding="utf-8").write("\n".join(L))
print("\n".join(L[:60]))
print(f"\n... tamamı UZUN_VADE_RAPORU.md ({len(L)} satir)")
