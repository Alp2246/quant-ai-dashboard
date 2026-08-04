import math

import numpy as np
import pandas as pd

from backtest import backtest_strategy
from monte_carlo import summarize


def test_summarize_uses_horizon_years_for_cagr():
    terminal = np.array([200.0, 200.0, 200.0])
    stats = summarize(
        terminal,
        S0=100.0,
        mu_adj=0.10,
        sigma_adj=0.40,
        horizon_years=5.0,
        fat_tail_cap_multiplier=20.0,
    )
    expected = ((2.0 ** (1 / 5.0)) - 1) * 100
    assert math.isclose(stats["cagr_median_pct"], round(expected, 2), abs_tol=1e-9)


def test_summarize_uses_cap_multiplier_for_cap_hit_metric():
    terminal = np.array([397.0, 401.0, 450.0])
    stats = summarize(
        terminal,
        S0=100.0,
        mu_adj=0.10,
        sigma_adj=0.40,
        horizon_years=10.0,
        fat_tail_cap_multiplier=4.0,
    )
    assert stats["cap_hit_threshold"] == 398.0
    assert stats["p_20x_cap_hit"] == round((2 / 3) * 100, 2)


def test_backtest_defaults_to_next_bar_open_entry():
    idx = pd.date_range("2024-01-01", periods=61, freq="B")
    close = np.linspace(100, 160, len(idx))
    open_ = close - 0.5
    high = close + 1.0
    low = close - 1.0

    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "rsi": np.full(len(idx), 55.0),
            "macd_hist": np.full(len(idx), 1.0),
            "sma_20": close - 1.0,
            "atr_14": np.full(len(idx), 100.0),
        },
        index=idx,
    )

    # Create a single buy signal on bar 30 and keep sell conditions inactive.
    df.loc[idx[29], "rsi"] = 49.0
    df.loc[idx[30], "rsi"] = 55.0
    df.loc[idx[29], "macd_hist"] = -1.0
    df.loc[idx[30], "macd_hist"] = 1.0

    res = backtest_strategy(
        df, holding_days=3, years=1, atr_sl_mult=10.0, atr_tp_mult=10.0,
        commission_bps=0.0, slippage_bps=0.0,
    )
    assert res["n_trades"] >= 1
    first_trade = res["trades"][0]
    assert first_trade["entry_date"] == idx[31]
    assert first_trade["entry_price_raw"] == round(float(df.loc[idx[31], "Open"]), 2)
    assert first_trade["entry_price"] == round(float(df.loc[idx[31], "Open"]), 2)


def test_backtest_moves_sat_exit_to_next_bar_open():
    idx = pd.date_range("2024-01-01", periods=61, freq="B")
    close = np.linspace(100, 160, len(idx))
    open_ = close - 0.5
    high = close + 1.0
    low = close - 1.0

    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "rsi": np.full(len(idx), 55.0),
            "macd_hist": np.full(len(idx), 1.0),
            "sma_20": close - 10.0,
            "atr_14": np.full(len(idx), 100.0),
        },
        index=idx,
    )

    # Buy signal
    df.loc[idx[29], "rsi"] = 49.0
    df.loc[idx[30], "rsi"] = 55.0
    df.loc[idx[29], "macd_hist"] = -1.0
    df.loc[idx[30], "macd_hist"] = 1.0

    # SAT signal on bar 35 via RSI > 65.
    df.loc[idx[35], "rsi"] = 70.0

    res = backtest_strategy(
        df, holding_days=20, years=1, atr_sl_mult=10.0, atr_tp_mult=10.0,
        commission_bps=0.0, slippage_bps=0.0,
    )
    first_trade = res["trades"][0]
    assert first_trade["exit_reason"] == "SAT"
    assert first_trade["exit_date"] == idx[36]
    assert first_trade["exit_price_raw"] == round(float(df.loc[idx[36], "Open"]), 2)
    assert first_trade["exit_price"] == round(float(df.loc[idx[36], "Open"]), 2)


def test_backtest_moves_time_exit_to_next_bar_open():
    idx = pd.date_range("2024-01-01", periods=61, freq="B")
    close = np.linspace(100, 160, len(idx))
    open_ = close - 0.5
    high = close + 1.0
    low = close - 1.0

    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "rsi": np.full(len(idx), 55.0),
            "macd_hist": np.full(len(idx), 1.0),
            "sma_20": close - 10.0,
            "atr_14": np.full(len(idx), 100.0),
        },
        index=idx,
    )

    # Buy signal
    df.loc[idx[29], "rsi"] = 49.0
    df.loc[idx[30], "rsi"] = 55.0
    df.loc[idx[29], "macd_hist"] = -1.0
    df.loc[idx[30], "macd_hist"] = 1.0

    res = backtest_strategy(
        df, holding_days=3, years=1, atr_sl_mult=10.0, atr_tp_mult=10.0,
        commission_bps=0.0, slippage_bps=0.0,
    )
    first_trade = res["trades"][0]
    assert first_trade["exit_reason"] == "TIME"
    assert first_trade["exit_date"] == idx[35]
    assert first_trade["exit_price_raw"] == round(float(df.loc[idx[35], "Open"]), 2)
    assert first_trade["exit_price"] == round(float(df.loc[idx[35], "Open"]), 2)


def test_backtest_applies_roundtrip_costs_to_returns():
    idx = pd.date_range("2024-01-01", periods=61, freq="B")
    close = np.linspace(100, 160, len(idx))
    open_ = close - 0.5
    high = close + 1.0
    low = close - 1.0

    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "rsi": np.full(len(idx), 55.0),
            "macd_hist": np.full(len(idx), 1.0),
            "sma_20": close - 10.0,
            "atr_14": np.full(len(idx), 100.0),
        },
        index=idx,
    )
    df.loc[idx[29], "rsi"] = 49.0
    df.loc[idx[30], "rsi"] = 55.0
    df.loc[idx[29], "macd_hist"] = -1.0
    df.loc[idx[30], "macd_hist"] = 1.0

    no_cost = backtest_strategy(
        df, holding_days=3, years=1, atr_sl_mult=10.0, atr_tp_mult=10.0,
        commission_bps=0.0, slippage_bps=0.0,
    )
    with_cost = backtest_strategy(
        df, holding_days=3, years=1, atr_sl_mult=10.0, atr_tp_mult=10.0,
        commission_bps=10.0, slippage_bps=5.0,
    )

    t0 = no_cost["trades"][0]
    t1 = with_cost["trades"][0]
    assert t1["entry_price"] > t1["entry_price_raw"]
    assert t1["exit_price"] < t1["exit_price_raw"]
    assert t1["return_pct"] < t0["return_pct"]
    assert t1["cost_bps_roundtrip"] == 30.0


def test_backtest_prefers_sl_when_sl_and_tp_hit_same_bar():
    idx = pd.date_range("2024-01-01", periods=61, freq="B")
    close = np.linspace(100, 160, len(idx))
    open_ = close - 0.5
    high = close + 1.0
    low = close - 1.0

    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "rsi": np.full(len(idx), 55.0),
            "macd_hist": np.full(len(idx), 1.0),
            "sma_20": close - 10.0,
            "atr_14": np.full(len(idx), 1.0),
        },
        index=idx,
    )
    df.loc[idx[29], "rsi"] = 49.0
    df.loc[idx[30], "rsi"] = 55.0
    df.loc[idx[29], "macd_hist"] = -1.0
    df.loc[idx[30], "macd_hist"] = 1.0

    # Entry happens on idx[31] open; keep the entry bar itself inside both
    # barriers, then force both barriers to hit on idx[32].
    df.loc[idx[31], "Low"] = df.loc[idx[31], "Open"] - 0.1
    df.loc[idx[31], "High"] = df.loc[idx[31], "Open"] + 0.1
    df.loc[idx[32], "Low"] = 40.0
    df.loc[idx[32], "High"] = 200.0

    res = backtest_strategy(
        df, holding_days=20, years=1, atr_sl_mult=1.0, atr_tp_mult=1.0,
        commission_bps=0.0, slippage_bps=0.0,
    )
    first_trade = res["trades"][0]
    assert first_trade["exit_reason"] == "SL"

