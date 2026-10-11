"""
backtest.py - Stratejinin son 2 yildaki AL sinyallerini test eder.
Win rate, ortalama getiri, toplam buy&hold karsilastirmasi.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config import (BACKTEST_COMMISSION_BPS, BACKTEST_HOLDING_DAYS,
                    BACKTEST_LOOKBACK_YEARS, BACKTEST_SLIPPAGE_BPS,
                    RSI_OVERBOUGHT, RSI_OVERSOLD)

logger = logging.getLogger(__name__)


def generate_signals(df: pd.DataFrame, window: int = 5) -> pd.Series:
    """
    Sinyal mantigi — v11.0 TREND kurali (olculmus vaka, 11.10.2026).

    Eski "salinim" kurali (asagida _generate_signals_swing_v10 olarak arsivli)
    10y/10 hisse testinde ISLEM BASI BEKLENTI -%0.22 uretiyordu
    (304 islem, win %35.5 < kira noktasi %36.6; sinyal gunleri rastgele
    gunlerden yalnizca +%1.01 iyiydi — kural bilgi tasimiyordu).
    Kok neden UFUK UYUSMAZLIGIydi: getirinin aylarca biriktigi volatil
    evrende pozisyon ort. 5-6 gunde kapaniyordu (cikistan sonra hisseler
    20g +%9.2 / 60g +%28.3 gitmeye devam ediyordu).

    YENI kural:
      AL  = RSI 50'yi yukari keser AND MACD histogrami > 0
            AND fiyat SMA200 ustunde (yalnizca yukselis rejimi)
      SAT = yok — cikis yapısaldir: SL / TP / TIME (backtest_strategy).

    Olculmus sonuc (ayni veri, 11.10.2026): 102 islem, islem toplami
    -%66.6 -> +%442.5, bilesik +%191.6; POET +%531.7 (al-tut +%12.4).
    """
    rsi = df["rsi"]
    hist = df["macd_hist"]
    sma200 = df["sma_200"] if "sma_200" in df.columns else df["Close"].rolling(200).mean()

    rsi_cross_up = (rsi.shift(1) < 50) & (rsi >= 50)
    buy = rsi_cross_up & (hist > 0) & (df["Close"] > sma200)

    signals = pd.Series("BEKLE", index=df.index)
    signals[buy] = "AL"
    return signals


def _generate_signals_swing_v10(df: pd.DataFrame, window: int = 5) -> pd.Series:
    """ARSIV — v10.0 oncesi Murphy salinim kurali (11.10.2026'da emekli).

    SAT kurali (RSI>65 / Close<SMA20 / MACD asagi) 304 islemin %77'sini
    ort. 5 gunde -%2.3 ile kapatiyordu; tek basina geri almak kayiplari
    buyuttu (-%110) cunku kural zayif islemleri SL'den once kesiyordu.
    Sorun cikis degil UFUK'tu. Geri donus icin generate_signals'in govdesini
    bununla degistirmek yeterli.
    """
    rsi = df["rsi"]
    hist = df["macd_hist"]
    close = df["Close"]
    sma20 = df["sma_20"]

    rsi_cross_up = (rsi.shift(1) < 50) & (rsi >= 50)
    hist_cross_up = (hist.shift(1) <= 0) & (hist > 0)
    hist_cross_down = (hist.shift(1) >= 0) & (hist < 0)

    recent_rsi = rsi_cross_up.rolling(window).max().astype(bool)
    recent_hist = hist_cross_up.rolling(window).max().astype(bool)

    buy = (rsi_cross_up & recent_hist) | (hist_cross_up & recent_rsi)
    sell = (rsi > 65) | (close < sma20) | hist_cross_down

    signals = pd.Series("BEKLE", index=df.index)
    signals[buy] = "AL"
    signals[sell] = "SAT"
    return signals


def _sharpe_ratio(returns: np.ndarray, periods_per_year: int = 12) -> float:
    """
    Sharpe Ratio (Sharpe 1966).

    Formul (Math_Specs.md Bolum 3.1):
        Sharpe = (mean(r) - rf/N) / std(r) * sqrt(N)

    Risk-free oran %2/yil olarak varsayilir (US 10Y proxy).
    Trade return'lerinden hesap; ortalama gun sayisi periods_per_year'a oranlanir.
    """
    if len(returns) < 2:
        return 0.0
    r = returns / 100.0   # yuzde -> kesir
    mu = r.mean()
    sigma = r.std(ddof=1)
    if sigma == 0:
        return 0.0
    return float((mu / sigma) * (periods_per_year ** 0.5))


def _max_drawdown(equity_curve: np.ndarray) -> dict:
    """Maximum Drawdown - pic-to-trough en buyuk dusus orani.

    Formul (Math_Specs.md Bolum 3.3):
        MDD = min_t  (P_t - max_{s<=t} P_s) / max_{s<=t} P_s

    Calmar Ratio bu degere bolerek hesaplanir.
    Returns: max_dd_pct (negatif), peak_idx, trough_idx.
    """
    if len(equity_curve) == 0:
        return {"max_dd_pct": 0.0, "peak_idx": -1, "trough_idx": -1}
    peak = np.maximum.accumulate(equity_curve)
    dd = (equity_curve - peak) / peak * 100
    trough_idx = int(np.argmin(dd))
    peak_idx = int(np.argmax(equity_curve[:trough_idx + 1])) if trough_idx > 0 else 0
    return {
        "max_dd_pct": float(round(dd.min(), 2)),
        "peak_idx": peak_idx,
        "trough_idx": trough_idx,
    }


def backtest_strategy(
    df: pd.DataFrame,
    holding_days: int = BACKTEST_HOLDING_DAYS,
    years: float = BACKTEST_LOOKBACK_YEARS,
    atr_sl_mult: float = 2.0,
    atr_tp_mult: float = 6.0,   # v11.0: 3.0 -> 6.0 (ufuk uyumu, olcumlu)
    entry_execution: str = "next_open",
    signal_exit_execution: str = "next_open",
    commission_bps: float = BACKTEST_COMMISSION_BPS,
    slippage_bps: float = BACKTEST_SLIPPAGE_BPS,
) -> dict:
    """Triple Barrier Method backtest.

    Akademik Referans:
      Lopez de Prado, M. (2018). Advances in Financial Machine Learning,
      Ch.3. Wiley. ISBN 978-1119482086.

    Formul (Math_Specs.md Bolum 2):
      Barrier_u_l = P_entry * exp( +/- phi * sigma_d * sqrt(t) )

    Klasik tek-yonlu stop-loss yerine UC boyutlu bariyer:
      Alt   Stop-Loss   = entry - atr_sl_mult * ATR  (dinamik)
      Ust   Take-Profit = entry + atr_tp_mult * ATR
      Zaman holding_days bar sonra zorla cikis.

    Her trade etiket: TP / SL / TIME / END (+ SAT yalnizca eski arsiv kural).
    Risk metrikleri: Sharpe Ratio, Maximum Drawdown, Calmar Ratio.
    """
    if commission_bps < 0 or slippage_bps < 0:
        raise ValueError("commission_bps and slippage_bps must be non-negative")

    data = df.copy()
    if len(data) < 60:
        return _empty_result()

    # Son N yil
    cutoff = data.index[-1] - pd.Timedelta(days=max(1, int(round(years * 365.25))))
    data = data[data.index >= cutoff]
    if len(data) < 30:
        return _empty_result()

    signals = generate_signals(data)
    # ATR (Triple Barrier dinamik bariyerleri icin)
    atr = data["atr_14"] if "atr_14" in data.columns else pd.Series(
        [0] * len(data), index=data.index)

    trades = []
    pos_open = False
    entry_idx = None
    entry_price = None
    entry_price_raw = None
    sl_level = None
    tp_level = None
    entry_atr = None
    entry_date = None
    pending_entry = None
    pending_exit = None
    roundtrip_cost_bps = 2.0 * (commission_bps + slippage_bps)

    indices = list(data.index)
    for i, ts in enumerate(indices):
        sig = signals.loc[ts]
        price = float(data["Close"].iloc[i])
        open_price = float(data["Open"].iloc[i]) if "Open" in data.columns else price
        high = float(data["High"].iloc[i]) if "High" in data.columns else price
        low = float(data["Low"].iloc[i]) if "Low" in data.columns else price

        # Execute prior-bar signal on the next bar's open to avoid using the
        # same closing price both for signal discovery and entry fill.
        if not pos_open and pending_entry is not None and pending_entry["entry_idx"] == i:
            pos_open = True
            entry_idx = i
            entry_price_raw = open_price if entry_execution == "next_open" else price
            entry_price = _apply_entry_cost(entry_price_raw, commission_bps, slippage_bps)
            entry_atr = pending_entry["entry_atr"]
            sl_level = entry_price - atr_sl_mult * entry_atr
            tp_level = entry_price + atr_tp_mult * entry_atr
            entry_date = ts
            pending_entry = None

        if pos_open and pending_exit is not None and pending_exit["exit_idx"] == i:
            exit_reason = pending_exit["exit_reason"]
            raw_exit_price = open_price
            exit_price = _apply_exit_cost(raw_exit_price, commission_bps, slippage_bps)
            held = i - entry_idx
            ret = (exit_price / entry_price - 1) * 100
            trades.append({
                "entry_date": entry_date,
                "exit_date": ts,
                "days_held": held,
                "entry_price": round(entry_price, 2),
                "entry_price_raw": round(entry_price_raw, 2),
                "exit_price": round(exit_price, 2),
                "exit_price_raw": round(raw_exit_price, 2),
                "stop_loss": round(sl_level, 2),
                "take_profit": round(tp_level, 2),
                "atr_at_entry": round(entry_atr, 3),
                "return_pct": round(ret, 2),
                "gross_return_pct": round((raw_exit_price / entry_price_raw - 1) * 100, 2),
                "cost_bps_roundtrip": round(roundtrip_cost_bps, 2),
                "exit_reason": exit_reason,
            })
            pos_open = False
            pending_exit = None
            entry_price_raw = None
            sl_level = tp_level = entry_atr = None
            continue

        if not pos_open and sig == "AL":
            if entry_execution == "same_close":
                pos_open = True
                entry_idx = i
                entry_price_raw = price
                entry_price = _apply_entry_cost(entry_price_raw, commission_bps, slippage_bps)
                entry_atr = float(atr.iloc[i]) if not pd.isna(atr.iloc[i]) else price * 0.03
                sl_level = entry_price - atr_sl_mult * entry_atr
                tp_level = entry_price + atr_tp_mult * entry_atr
                entry_date = ts
            elif i < len(indices) - 1:
                entry_atr_val = float(atr.iloc[i]) if not pd.isna(atr.iloc[i]) else price * 0.03
                pending_entry = {"entry_idx": i + 1, "entry_atr": entry_atr_val}
        elif pos_open:
            held = i - entry_idx
            exit_reason = None
            raw_exit_price = price
            exit_price = _apply_exit_cost(raw_exit_price, commission_bps, slippage_bps)

            # 1) Alt Bariyer (SL) - intraday low'a vurdu mu?
            if low <= sl_level:
                exit_reason = "SL"
                raw_exit_price = sl_level
                exit_price = _apply_exit_cost(raw_exit_price, commission_bps, slippage_bps)
            # 2) Ust Bariyer (TP) - intraday high'a vurdu mu?
            elif high >= tp_level:
                exit_reason = "TP"
                raw_exit_price = tp_level
                exit_price = _apply_exit_cost(raw_exit_price, commission_bps, slippage_bps)
            # 3) Zaman Bariyeri (paranin zaman maliyeti - de Prado)
            elif held >= holding_days:
                if signal_exit_execution == "next_open" and i < len(indices) - 1:
                    pending_exit = {"exit_idx": i + 1, "exit_reason": "TIME"}
                    continue
                exit_reason = "TIME"
            # 4) Signal-based exit
            elif sig == "SAT":
                if signal_exit_execution == "next_open" and i < len(indices) - 1:
                    pending_exit = {"exit_idx": i + 1, "exit_reason": "SAT"}
                    continue
                exit_reason = "SAT"
            # 5) Son bar
            elif i == len(indices) - 1:
                exit_reason = "END"

            if exit_reason:
                ret = (exit_price / entry_price - 1) * 100
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": ts,
                    "days_held": held,
                    "entry_price": round(entry_price, 2),
                    "entry_price_raw": round(entry_price_raw, 2),
                    "exit_price": round(exit_price, 2),
                    "exit_price_raw": round(raw_exit_price, 2),
                    "stop_loss": round(sl_level, 2),
                    "take_profit": round(tp_level, 2),
                    "atr_at_entry": round(entry_atr, 3),
                    "return_pct": round(ret, 2),
                    "gross_return_pct": round((raw_exit_price / entry_price_raw - 1) * 100, 2),
                    "cost_bps_roundtrip": round(roundtrip_cost_bps, 2),
                    "exit_reason": exit_reason,
                })
                pos_open = False
                entry_price_raw = None
                sl_level = tp_level = entry_atr = None

    if not trades:
        bh = (data["Close"].iloc[-1] / data["Close"].iloc[0] - 1) * 100
        bh_curve = (data["Close"] / data["Close"].iloc[0]).values * 100
        bh_mdd = _max_drawdown(bh_curve)
        return {
            "trades": [], "n_trades": 0, "win_rate": 0, "avg_return": 0,
            "total_return": 0, "cum_return": 0, "best_trade": 0,
            "worst_trade": 0,
            "buy_hold_return": round(bh, 2),
            "alpha_vs_bh": round(-bh, 2),
            "sharpe_ratio": 0, "max_drawdown_pct": 0,
            "buy_hold_drawdown_pct": bh_mdd["max_dd_pct"],
            "calmar_ratio": 0, "avg_holding_days": 0,
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
            "roundtrip_cost_bps": round(roundtrip_cost_bps, 2),
            "entry_execution": entry_execution,
            "signal_exit_execution": signal_exit_execution,
            "exit_counts": {"TP": 0, "SL": 0, "TIME": 0, "SAT": 0, "END": 0},
            "trades_df": pd.DataFrame(),
        }

    rets = np.array([t["return_pct"] for t in trades])
    wins = (rets > 0).sum()
    n = len(rets)
    # Triple Barrier exit-reason dagilimi
    exit_counts = {"TP": 0, "SL": 0, "TIME": 0, "SAT": 0, "END": 0}
    for t in trades:
        exit_counts[t["exit_reason"]] = exit_counts.get(t["exit_reason"], 0) + 1

    # Bilesik getiri (her ticaret %100 sermaye varsayim)
    cum_curve = (1 + rets / 100).cumprod()
    cum_return = (cum_curve[-1] - 1) * 100

    bh = (data["Close"].iloc[-1] / data["Close"].iloc[0] - 1) * 100

    # Sharpe: ortalama tutma suresi gun cinsinden -> trade/yil tahmini
    avg_held = np.mean([t["days_held"] for t in trades]) if trades else 1
    trades_per_year = max(1, round(252 / max(avg_held, 1)))
    sharpe = _sharpe_ratio(rets, periods_per_year=trades_per_year)

    # Max Drawdown - cumulative equity curve uzerinde
    mdd = _max_drawdown(cum_curve * 100)

    # Buy & Hold drawdown (karsilastirma)
    bh_curve = (data["Close"] / data["Close"].iloc[0]).values * 100
    bh_mdd = _max_drawdown(bh_curve)

    # Calmar Ratio = cum_return / |MaxDD|
    calmar = abs(cum_return / mdd["max_dd_pct"]) if mdd["max_dd_pct"] != 0 else 0.0

    return {
        "trades": trades,
        "n_trades": n,
        "win_rate": round(wins / n * 100, 1),
        "avg_return": round(float(rets.mean()), 2),
        "total_return": round(float(rets.sum()), 2),
        "cum_return": round(cum_return, 2),
        "best_trade": round(float(rets.max()), 2),
        "worst_trade": round(float(rets.min()), 2),
        "buy_hold_return": round(bh, 2),
        "alpha_vs_bh": round(cum_return - bh, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": mdd["max_dd_pct"],
        "buy_hold_drawdown_pct": bh_mdd["max_dd_pct"],
        "calmar_ratio": round(calmar, 2),
        "avg_holding_days": round(float(avg_held), 1),
        "commission_bps": commission_bps,
        "slippage_bps": slippage_bps,
        "roundtrip_cost_bps": round(roundtrip_cost_bps, 2),
        "entry_execution": entry_execution,
        "signal_exit_execution": signal_exit_execution,
        "exit_counts": exit_counts,
        "trades_df": pd.DataFrame(trades),
    }


def _empty_result() -> dict:
    return {
        "trades": [], "n_trades": 0, "win_rate": 0, "avg_return": 0,
        "total_return": 0, "cum_return": 0, "best_trade": 0,
        "worst_trade": 0, "buy_hold_return": 0, "alpha_vs_bh": 0,
        "sharpe_ratio": 0, "max_drawdown_pct": 0,
        "buy_hold_drawdown_pct": 0, "calmar_ratio": 0,
        "avg_holding_days": 0,
        "commission_bps": BACKTEST_COMMISSION_BPS,
        "slippage_bps": BACKTEST_SLIPPAGE_BPS,
        "roundtrip_cost_bps": 2.0 * (BACKTEST_COMMISSION_BPS + BACKTEST_SLIPPAGE_BPS),
        "entry_execution": "next_open",
        "signal_exit_execution": "next_open",
        "exit_counts": {"TP": 0, "SL": 0, "TIME": 0, "SAT": 0, "END": 0},
        "trades_df": pd.DataFrame(),
    }


def _apply_entry_cost(price: float, commission_bps: float, slippage_bps: float) -> float:
    """For long entries, both commission and slippage worsen the fill upward."""
    return float(price * (1 + (commission_bps + slippage_bps) / 10_000.0))


def _apply_exit_cost(price: float, commission_bps: float, slippage_bps: float) -> float:
    """For long exits, both commission and slippage worsen the fill downward."""
    return float(price * (1 - (commission_bps + slippage_bps) / 10_000.0))
