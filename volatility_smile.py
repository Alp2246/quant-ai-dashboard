"""
volatility_smile.py - Opsiyon piyasasindan Implied Volatility cek + Korku Endeksi.

yfinance .option_chain() ATM (at-the-money) IV verir. OTM put IV / OTM call IV
karsilastirmasi 'volatility skew' -> piyasanin korku seviyesi.

Yuksek IV + asimmetrik skew (put-heavy) = korku yuksek.
"""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def _safe(v, default=np.nan):
    try:
        f = float(v)
        if f != f:
            return default
        return f
    except (TypeError, ValueError):
        return default


def get_implied_volatility(ticker: str, max_expirations: int = 2) -> dict:
    """
    En yakin 1-2 opsiyon vadesinin ATM IV'sini hesaplar +
    OTM put / OTM call IV skew (korku gostergesi).

    Returns:
      {
        atm_iv_pct, put_iv_pct, call_iv_pct,
        skew_pct (put - call), fear_level, fear_label,
        nearest_expiry, n_contracts, success
      }
    """
    try:
        t = yf.Ticker(ticker)
        expirations = list(t.options or [])
    except Exception as e:
        logger.warning("%s options listesi hata: %s", ticker, e)
        return _empty_iv(ticker, str(e))

    if not expirations:
        return _empty_iv(ticker, "Opsiyon zinciri yok")

    # Hisse fiyati
    try:
        spot = float(t.fast_info.last_price)
    except Exception:
        try:
            spot = float(t.history(period="1d")["Close"].iloc[-1])
        except Exception:
            return _empty_iv(ticker, "Spot fiyat alinamadi")

    if spot <= 0:
        return _empty_iv(ticker, "Spot 0")

    iv_atm_list = []
    iv_put_list = []
    iv_call_list = []
    nearest = None
    total_contracts = 0

    for exp in expirations[:max_expirations]:
        try:
            chain = t.option_chain(exp)
        except Exception as e:
            logger.debug("%s exp=%s chain hata: %s", ticker, exp, e)
            continue
        calls = chain.calls
        puts = chain.puts
        if calls is None or calls.empty:
            continue
        nearest = nearest or exp
        total_contracts += len(calls) + (len(puts) if puts is not None else 0)

        # ATM = strike spot'a en yakin
        def _pick(df, mode="atm"):
            if df is None or df.empty or "impliedVolatility" not in df.columns:
                return np.nan
            d = df.dropna(subset=["impliedVolatility"]).copy()
            if d.empty:
                return np.nan
            if mode == "atm":
                idx = (d["strike"] - spot).abs().idxmin()
            elif mode == "otm_put":
                otm = d[d["strike"] < spot * 0.95]
                if otm.empty:
                    return np.nan
                idx = (otm["strike"] - spot * 0.90).abs().idxmin()
            elif mode == "otm_call":
                otm = d[d["strike"] > spot * 1.05]
                if otm.empty:
                    return np.nan
                idx = (otm["strike"] - spot * 1.10).abs().idxmin()
            return _safe(d.loc[idx, "impliedVolatility"])

        # ATM IV: call ve put ortalamasi
        c_atm = _pick(calls, "atm")
        p_atm = _pick(puts, "atm")
        if not np.isnan(c_atm) and not np.isnan(p_atm):
            iv_atm_list.append((c_atm + p_atm) / 2)
        elif not np.isnan(c_atm):
            iv_atm_list.append(c_atm)
        elif not np.isnan(p_atm):
            iv_atm_list.append(p_atm)

        # OTM put/call
        otm_p = _pick(puts, "otm_put")
        otm_c = _pick(calls, "otm_call")
        if not np.isnan(otm_p):
            iv_put_list.append(otm_p)
        if not np.isnan(otm_c):
            iv_call_list.append(otm_c)

    if not iv_atm_list:
        return _empty_iv(ticker, "ATM IV bulunamadi")

    atm_iv = float(np.mean(iv_atm_list)) * 100
    put_iv = float(np.mean(iv_put_list)) * 100 if iv_put_list else atm_iv
    call_iv = float(np.mean(iv_call_list)) * 100 if iv_call_list else atm_iv
    skew = put_iv - call_iv

    # Fear level (heuristic):
    # - ATM IV yuksek (>%80) + put skew (>+5pp) = panik
    # - ATM IV orta (%40-80) + put skew dengeli = normal
    fear_score = min(100, max(0, (atm_iv - 30) * 0.6 + max(0, skew) * 4))
    if fear_score >= 70:
        fear_label = "🚨 PANIK"
    elif fear_score >= 50:
        fear_label = "⚠️ KORKU YUKSEK"
    elif fear_score >= 30:
        fear_label = "😐 NORMAL"
    elif fear_score >= 15:
        fear_label = "😌 SAKIN"
    else:
        fear_label = "🟢 DUSUK VOLATILITE"

    return {
        "ticker": ticker,
        "spot": round(spot, 2),
        "atm_iv_pct": round(atm_iv, 1),
        "put_iv_pct": round(put_iv, 1),
        "call_iv_pct": round(call_iv, 1),
        "skew_pp": round(skew, 1),
        "fear_score": round(fear_score, 1),
        "fear_label": fear_label,
        "nearest_expiry": nearest,
        "n_contracts": total_contracts,
        "success": True,
    }


def _empty_iv(ticker, reason="") -> dict:
    return {
        "ticker": ticker, "spot": 0,
        "atm_iv_pct": 0, "put_iv_pct": 0, "call_iv_pct": 0,
        "skew_pp": 0, "fear_score": 0, "fear_label": "VERI YOK",
        "nearest_expiry": None, "n_contracts": 0,
        "success": False, "reason": reason,
    }
