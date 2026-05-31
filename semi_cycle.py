"""
semi_cycle.py - Yari Iletken Dongusunun Fazini Tespit Et.

Phase: Downturn -> Trough -> Recovery -> Expansion -> Peak -> ...

Yontem (literatur-dayali):
  1) SOXX (iShares Semi ETF) ve SMH (VanEck Semi ETF) son 252 gun
  2) Fiyat / 200-gunluk SMA (uzun trend)
  3) RSI(60) - orta vade momentum
  4) 12-ay performans vs 36-ay performans
  5) Booking-to-bill proxy: NVDA + ASML + AMAT haftalik volume zigzag
  6) Inventory cycle proxy: MU + INTC trend

Cikti: phase, cycle_score 0..100 (0=trough, 100=peak),
modifier -3..+3 (Master Score'a)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


SEMI_PROXIES = ["SOXX", "SMH"]
EQUIPMENT_PROXIES = ["ASML", "AMAT", "LRCX"]
MEMORY_PROXIES = ["MU", "WDC"]
LOGIC_PROXIES = ["NVDA", "TSM", "AMD"]


def _safe_last(series, default=np.nan):
    try:
        if series is None or len(series) == 0:
            return default
        v = float(series.iloc[-1])
        return v if v == v else default
    except Exception:
        return default


def _trend_metrics(ticker: str) -> dict:
    try:
        df = yf.Ticker(ticker).history(period="3y", interval="1d")
        if df is None or df.empty:
            return {}
        close = df["Close"]
        sma200 = close.rolling(200).mean()
        sma50 = close.rolling(50).mean()
        delta = close.diff()
        up = delta.clip(lower=0).rolling(60).mean()
        down = (-delta.clip(upper=0)).rolling(60).mean()
        rs = up / down.replace(0, np.nan)
        rsi60 = 100 - 100 / (1 + rs)

        last = float(close.iloc[-1])
        sma200_v = _safe_last(sma200, last)
        sma50_v = _safe_last(sma50, last)
        rsi_v = _safe_last(rsi60, 50)

        ret_12m = ((float(close.iloc[-1]) / float(close.iloc[-252])) - 1) * 100 \
                    if len(close) >= 252 else 0
        ret_36m = ((float(close.iloc[-1]) / float(close.iloc[0])) - 1) * 100 \
                    if len(close) >= 600 else ret_12m

        return {
            "close": last,
            "sma_200": sma200_v,
            "sma_50": sma50_v,
            "above_200": last > sma200_v if not np.isnan(sma200_v) else None,
            "above_50": last > sma50_v if not np.isnan(sma50_v) else None,
            "rsi_60": rsi_v,
            "ret_12m_pct": ret_12m,
            "ret_36m_pct": ret_36m,
        }
    except Exception as e:
        logger.debug("trend metric %s: %s", ticker, e)
        return {}


def detect_cycle_phase() -> dict:
    """
    Yari iletken dongu fazini tespit et.

    Returns:
      {
        phase: 'Trough'|'Recovery'|'Expansion'|'Peak'|'Downturn',
        cycle_score: 0..100,
        modifier: -3..+3,  (Master Score'a etki)
        signals: {soxx, smh, equipment_avg, memory_avg, logic_avg},
        narrative: str,
        scanned_at: iso
      }
    """
    from datetime import datetime, timezone

    soxx = _trend_metrics("SOXX")
    smh = _trend_metrics("SMH")

    # Endustri segment ortalamalari
    def _avg(tickers):
        rets, rsis, above200 = [], [], []
        for t in tickers:
            m = _trend_metrics(t)
            if not m:
                continue
            rets.append(m.get("ret_12m_pct", 0))
            rsis.append(m.get("rsi_60", 50))
            if m.get("above_200") is not None:
                above200.append(1 if m["above_200"] else 0)
        return {
            "ret_12m_pct": float(np.mean(rets)) if rets else 0,
            "rsi_60": float(np.mean(rsis)) if rsis else 50,
            "above_200_pct": float(np.mean(above200) * 100) if above200 else 50,
        }

    eq = _avg(EQUIPMENT_PROXIES)
    mem = _avg(MEMORY_PROXIES)
    logic = _avg(LOGIC_PROXIES)

    # Score 0..100: 4 sinyal aggregate
    # 1) SOXX RSI(60) (0..100)
    soxx_rsi = soxx.get("rsi_60", 50)
    smh_rsi = smh.get("rsi_60", 50)
    rsi_avg = (soxx_rsi + smh_rsi) / 2

    # 2) Equipment 12m return scale (-50% -> 0; +100% -> 100)
    eq_ret = eq.get("ret_12m_pct", 0)
    eq_score = max(0, min(100, (eq_ret + 50) / 150 * 100))

    # 3) Logic 12m return
    logic_ret = logic.get("ret_12m_pct", 0)
    logic_score = max(0, min(100, (logic_ret + 50) / 150 * 100))

    # 4) Above-200 SMA breadth
    breadth = (eq.get("above_200_pct", 50) +
                logic.get("above_200_pct", 50) +
                mem.get("above_200_pct", 50)) / 3

    cycle_score = round(rsi_avg * 0.3 + eq_score * 0.3 + logic_score * 0.25 +
                          breadth * 0.15, 1)

    # Faz tespiti + macro_bonus (kullanici talebi: Expansion = +10 Makro Bonus)
    if cycle_score >= 85:
        phase = "🔥 PEAK (Asiri Isinma)"
        modifier = -3
        macro_bonus = -5
        narrative = ("Sektor pikinde - geri donus yakin. Yeni alimlar icin "
                      "DCA stratejisine geç, yuksek pozisyonlari hafiflet.")
    elif cycle_score >= 65:
        phase = "📈 EXPANSION (Boga)"
        modifier = +2
        macro_bonus = +10   # <-- KULLANICI TALEBI: +10 MAKRO BONUS
        narrative = ("Sektor expansiyonda. Lider hisseler ASML/NVDA momentumda. "
                      "Trend takip stratejisi optimal. Teknoloji hisselerine "
                      "+10 Makro Bonus uygulanir.")
    elif cycle_score >= 40:
        phase = "🌅 RECOVERY (Toparlanma)"
        modifier = +3
        macro_bonus = +5
        narrative = ("Trough'tan cikis. Geride kalan hisseler (WOLF, RGTI) "
                      "yakaland alim noktasi. Risk/odul oranı en iyi.")
    elif cycle_score >= 20:
        phase = "🌧 TROUGH (Dip)"
        modifier = +1
        macro_bonus = 0
        narrative = ("Dipte fakat sinyaller karisik. Birikim donemi. "
                      "Yuksek kaliteli hisseler (ASML, NVDA) DCA icin uygun.")
    else:
        phase = "❄️ DOWNTURN (Resesyon)"
        modifier = -2
        macro_bonus = -10
        narrative = ("Cyclical downturn. Inventory correction surdurüyor. "
                      "Yeni pozisyon kesin avoid, mevcut pozisyonlarda stop-loss.")

    return {
        "phase": phase,
        "cycle_score": cycle_score,
        "modifier": modifier,
        "macro_bonus": macro_bonus,
        "narrative": narrative,
        "signals": {
            "soxx_rsi60": round(soxx_rsi, 1),
            "smh_rsi60": round(smh_rsi, 1),
            "equipment_12m_pct": round(eq.get("ret_12m_pct", 0), 2),
            "logic_12m_pct": round(logic.get("ret_12m_pct", 0), 2),
            "memory_12m_pct": round(mem.get("ret_12m_pct", 0), 2),
            "above_200_breadth_pct": round(breadth, 1),
        },
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
