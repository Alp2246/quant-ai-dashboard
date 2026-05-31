"""
backtest.py - Stratejinin son 2 yildaki AL sinyallerini test eder.
Win rate, ortalama getiri, toplam buy&hold karsilastirmasi.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config import RSI_OVERBOUGHT, RSI_OVERSOLD

logger = logging.getLogger(__name__)


def generate_signals(df: pd.DataFrame, window: int = 5) -> pd.Series:
    """
    Sinyal mantigi (John J. Murphy - Technical Analysis of the Financial Markets,
    Trend Takip stratejisi):

      AL  = ( RSI 50'yi yukari keser ) AND
            ( MACD histogrami negatiften pozitife doner )
            -- ikisinin 'window' bar icinde olmasi yeterli
      SAT = (RSI > 65) OR (Close < SMA20) OR (MACD hist > 0'dan < 0'a doner)

    Bu yaklasim "saglikli duzeltme" sonrasi yukari donen trendi yakalar;
    teknoloji bogalarinda (WOLF/IONQ) ekstrem dusus beklemekten kacinir.
    """
    rsi = df["rsi"]
    hist = df["macd_hist"]
    close = df["Close"]
    sma20 = df["sma_20"]

    # Crossover detection
    rsi_cross_up = (rsi.shift(1) < 50) & (rsi >= 50)
    hist_cross_up = (hist.shift(1) <= 0) & (hist > 0)
    hist_cross_down = (hist.shift(1) >= 0) & (hist < 0)

    # 'window' bar icinde her ikisinin gerceklesmesi (yumusak AND)
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
    holding_days: int = 20,
    years: float = 2,
    atr_sl_mult: float = 2.0,
    atr_tp_mult: float = 3.0,
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

    Her trade etiket: TP / SL / TIME / SAT.
    Risk metrikleri: Sharpe Ratio, Maximum Drawdown, Calmar Ratio.
    """
    data = df.copy()
    if len(data) < 60:
        return _empty_result()

    # Son N yil
    cutoff = data.index[-1] - pd.DateOffset(years=int(years))
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
    sl_level = None
    tp_level = None
    entry_atr = None
    entry_date = None

    indices = list(data.index)
    for i, ts in enumerate(indices):
        sig = signals.loc[ts]
        price = float(data["Close"].iloc[i])
        high = float(data["High"].iloc[i]) if "High" in data.columns else price
        low = float(data["Low"].iloc[i]) if "Low" in data.columns else price

        if not pos_open and sig == "AL":
            pos_open = True
            entry_idx = i
            entry_price = price
            entry_atr = float(atr.iloc[i]) if not pd.isna(atr.iloc[i]) else price * 0.03
            sl_level = entry_price - atr_sl_mult * entry_atr
            tp_level = entry_price + atr_tp_mult * entry_atr
            entry_date = ts
        elif pos_open:
            held = i - entry_idx
            exit_reason = None
            exit_price = price

            # 1) Alt Bariyer (SL) - intraday low'a vurdu mu?
            if low <= sl_level:
                exit_reason = "SL"
                exit_price = sl_level
            # 2) Ust Bariyer (TP) - intraday high'a vurdu mu?
            elif high >= tp_level:
                exit_reason = "TP"
                exit_price = tp_level
            # 3) Zaman Bariyeri (paranin zaman maliyeti - de Prado)
            elif held >= holding_days:
                exit_reason = "TIME"
            # 4) Signal-based exit
            elif sig == "SAT":
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
                    "exit_price": round(exit_price, 2),
                    "stop_loss": round(sl_level, 2),
                    "take_profit": round(tp_level, 2),
                    "atr_at_entry": round(entry_atr, 3),
                    "return_pct": round(ret, 2),
                    "exit_reason": exit_reason,
                })
                pos_open = False
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
        "exit_counts": {"TP": 0, "SL": 0, "TIME": 0, "SAT": 0, "END": 0},
        "trades_df": pd.DataFrame(),
    }
