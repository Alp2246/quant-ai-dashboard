# -*- coding: utf-8 -*-
"""radar_scanner.py - Birlesik erken uyarI radarI (v11.3).

SNDK vakasinin dersi: hisse listeye girene kadar kimse bakmadi. Bu modul
TUM listeleri (cekirdek + watchlist + darbogaz + Cin) ayni gunluk taramadan
gecirip "NVIDIA gibi hareketi erken yakalama" adaylarini siralar.

Sinyal bayraklari (her hisse icin 1y gunluk bar):
  hacim_patlamasi : son hacim >= 2 x 20g ort hacim (ilgi basladi)
  momentum_20g    : son 20 is gunu getirisi >= %15
  trend_ustu      : kapanis > SMA50 (dusen bicak degil)
  zirveye_yakin   : kapanis >= 52h zirvenin %%80'i (kiris hazirligi)
  yeni_listeleme  : < 250 is gunu gecmisi (SNDK/CBRS/NBIS kalibi)
  darbogaz        : BOTTLENECK_WATCHLIST uyesi (tez kapsiyor)

puan = agirlikli bayrak toplami; ustune MIN_AVG_DOLLAR_VOL likidite
filtresi dusuk olanlari "dusuk_likidite" diye damgar (kucuk hesaplar
icin spread/fisilti riski).

Sonuc data/radar_scan.json'a 6 saat TTL ile cache'lenir; Streamlit sekmesi
ag cagrisi yapmadan once cache'e bakar. Boylece panel her 15 dk'lik
yenilemede ~40 hisse indirmez.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from config import (ALL_WATCHLIST_DEFAULTS, BOTTLENECK_WATCHLIST,
                    CORE_TICKERS, DATA_DIR, TICKERS)

logger = logging.getLogger(__name__)

CACHE_FILE = DATA_DIR / "radar_scan.json"
CACHE_TTL_HOURS = 6
MIN_AVG_DOLLAR_VOL = 5_000_000     # 20g ort. hacim x fiyat < $5M ise damga
VOL_SPIKE_MULT = 2.0
MOM_20D_MIN_PCT = 15.0
NEAR_HIGH_RATIO = 0.80
NEW_LISTING_BARS = 250

WEIGHTS = {"hacim_patlamasi": 2, "momentum_20g": 2, "trend_ustu": 1,
           "zirveye_yakin": 1, "yeni_listeleme": 1, "darbogaz": 1}


def universe() -> list[str]:
    seen: dict[str, None] = {}
    for lst in (TICKERS, CORE_TICKERS, BOTTLENECK_WATCHLIST,
                ALL_WATCHLIST_DEFAULTS):
        for t in lst:
            seen.setdefault(t)
    return list(seen)


def membership(t: str) -> str:
    if t in CORE_TICKERS:
        return "CEKIRDEK"
    if t in BOTTLENECK_WATCHLIST:
        return "DARBOGAZ"
    return "WATCHLIST"


def _history(ticker: str) -> pd.DataFrame | None:
    import yfinance as yf
    try:
        df = yf.Ticker(ticker).history(period="1y", interval="1d",
                                       auto_adjust=True)
        return df if df is not None and len(df) >= 30 else None
    except Exception as e:
        logger.warning("%s veri hatasi: %s", ticker, e)
        return None


def scan_row(ticker: str, df: pd.DataFrame) -> dict:
    """Tek hissenin bayraklarini hesapla (ag'siz, test edilebilir)."""
    close = df["Close"].astype(float)
    vol = df["Volume"].astype(float) if "Volume" in df else pd.Series(
        0.0, index=df.index)
    last = float(close.iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 \
        else float(close.mean())
    vol_avg20 = float(vol.rolling(20).mean().iloc[-1])
    vol_last = float(vol.iloc[-1])
    mom20 = (last / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0.0
    high_52w = float(close.max())
    avg_dollar_vol = float((close * vol).rolling(20).mean().iloc[-1])

    flags = {
        "hacim_patlamasi": vol_avg20 > 0 and vol_last >= VOL_SPIKE_MULT * vol_avg20,
        "momentum_20g": mom20 >= MOM_20D_MIN_PCT,
        "trend_ustu": last > sma50,
        "zirveye_yakin": high_52w > 0 and last >= NEAR_HIGH_RATIO * high_52w,
        "yeni_listeleme": len(close) < NEW_LISTING_BARS,
        "darbogaz": ticker in BOTTLENECK_WATCHLIST,
    }
    score = sum(WEIGHTS[k] for k, v in flags.items() if v)
    return {
        "ticker": ticker,
        "liste": membership(ticker),
        "fiyat": round(last, 2),
        "mom_20g_pct": round(mom20, 1),
        "hacim_orani": round(vol_last / vol_avg20, 2) if vol_avg20 > 0 else None,
        "zirveden_uzaklik_pct": round((last / high_52w - 1) * 100, 1)
        if high_52w > 0 else None,
        "islem_gunu": len(close),
        "dusuk_likidite": avg_dollar_vol < MIN_AVG_DOLLAR_VOL,
        **{k: bool(v) for k, v in flags.items()},
        "puan": score,
    }


def scan(force: bool = False,
         history_fn=None,
         tickers: list[str] | None = None) -> dict:
    """Evreni tara. Cache tazeyse onu dondur (force=True bypass)."""
    if not force and CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(cached["scanned_at"]
                                        .replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - ts < timedelta(hours=CACHE_TTL_HOURS):
                return cached
        except Exception:
            pass  # bozuk cache -> yeniden tara

    if history_fn is None:
        history_fn = _history

    rows, errors = [], []
    for t in tickers or universe():
        try:
            df = history_fn(t)
            if df is None:
                continue
            rows.append(scan_row(t, df))
        except Exception as e:
            errors.append(f"{t}: {e}")
    rows.sort(key=lambda r: r["puan"], reverse=True)
    out = {"scanned_at": datetime.now(timezone.utc)
           .isoformat(timespec="seconds"),
           "n_scanned": len(rows), "errors": errors, "rows": rows,
           "weights": WEIGHTS}
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(out, indent=1, ensure_ascii=False),
                          encoding="utf-8")
    return out


def adaylar(scan_result: dict, min_puan: int = 3) -> list[dict]:
    """Panele gidecek kisa liste: puan esigi + en guncel bayraklar."""
    return [r for r in scan_result.get("rows", []) if r["puan"] >= min_puan]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    res = scan()
    print(json.dumps({k: (len(v) if isinstance(v, list) else v)
                      for k, v in res.items() if k != "rows"},
                     ensure_ascii=False, indent=1))
    for r in adaylar(res)[:15]:
        aktif = [k for k in WEIGHTS if r.get(k)]
        print(f"{r['ticker']:<8} puan={r['puan']} {r['liste']:<10} "
              f"mom20={r['mom_20g_pct']:+.1f}%  bayraklar={','.join(aktif)}")
