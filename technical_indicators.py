"""
technical_indicators.py - RSI, MACD ve diger teknik gostergeler
"""
import pandas as pd
import numpy as np


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "macd_signal": signal_line, "macd_hist": histogram}
    )


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range - volatilite olcusu."""
    high = df["High"]
    low = df["Low"]
    close_prev = df["Close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - close_prev).abs(),
        (low - close_prev).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()


def compute_stop_take(close: float, atr: float,
                      stop_mult: float = 2.0,
                      take_mult: float = 3.0) -> dict:
    """ATR tabanli dinamik stop-loss ve take-profit seviyeleri."""
    if atr <= 0 or close <= 0:
        return {"stop_loss": close, "take_profit": close,
                "stop_pct": 0, "take_pct": 0, "rr_ratio": 0}
    sl = close - stop_mult * atr
    tp = close + take_mult * atr
    return {
        "stop_loss": round(sl, 2),
        "take_profit": round(tp, 2),
        "stop_pct": round((close - sl) / close * 100, 2),
        "take_pct": round((tp - close) / close * 100, 2),
        "rr_ratio": round(take_mult / stop_mult, 2),
    }


def risk_label(atr_pct: float) -> str:
    """ATR% -> risk etiketi."""
    if atr_pct >= 7:
        return "COK YUKSEK RISK"
    if atr_pct >= 4:
        return "YUKSEK RISK"
    if atr_pct >= 2:
        return "ORTA RISK"
    return "DUSUK RISK"


def compute_bollinger(close: pd.Series, period: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands - ta-lib best practice."""
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    band_width = (upper - lower) / sma * 100
    pct_b = (close - lower) / (upper - lower)
    return pd.DataFrame({
        "bb_upper": upper, "bb_middle": sma, "bb_lower": lower,
        "bb_width": band_width, "bb_pctB": pct_b,
    })


def add_indicators(df: pd.DataFrame, rsi_period: int = 14) -> pd.DataFrame:
    """OHLCV DataFrame'e teknik kolonlar ekler."""
    out = df.copy()
    close = out["Close"]
    out["rsi"] = compute_rsi(close, rsi_period)
    macd = compute_macd(close)
    out = out.join(macd)
    out["sma_20"] = close.rolling(20).mean()
    out["sma_50"] = close.rolling(50).mean()
    out["sma_200"] = close.rolling(200).mean()
    out["returns_1d"] = close.pct_change()
    out["volatility_20"] = out["returns_1d"].rolling(20).std() * np.sqrt(252)
    out["atr_14"] = compute_atr(out, period=14)
    out["atr_pct"] = out["atr_14"] / close * 100
    bb = compute_bollinger(close)
    out = out.join(bb)
    return out


def latest_technical_snapshot(df: pd.DataFrame) -> dict:
    """Son bar icin teknik ozet."""
    row = df.dropna(subset=["rsi", "macd"]).iloc[-1] if len(df.dropna(subset=["rsi"])) else df.iloc[-1]
    rsi = float(row.get("rsi", 50))
    macd = float(row.get("macd", 0))
    macd_sig = float(row.get("macd_signal", 0))
    hist = float(row.get("macd_hist", 0))

    if rsi < 35:
        rsi_signal = "oversold"
    elif rsi > 70:
        rsi_signal = "overbought"
    else:
        rsi_signal = "neutral"

    macd_signal = "bullish" if macd > macd_sig and hist > 0 else (
        "bearish" if macd < macd_sig and hist < 0 else "neutral"
    )

    close_val = float(row["Close"])
    atr = float(row.get("atr_14", 0) or 0)
    atr_pct = float(row.get("atr_pct", 0) or 0)
    levels = compute_stop_take(close_val, atr)

    return {
        "rsi": rsi,
        "rsi_signal": rsi_signal,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": hist,
        "close": close_val,
        "sma_20": float(row.get("sma_20", close_val)),
        "sma_50": float(row.get("sma_50", close_val)),
        "atr": round(atr, 3),
        "atr_pct": round(atr_pct, 2),
        "risk_label": risk_label(atr_pct),
        "stop_loss": levels["stop_loss"],
        "take_profit": levels["take_profit"],
        "stop_pct": levels["stop_pct"],
        "take_pct": levels["take_pct"],
        "rr_ratio": levels["rr_ratio"],
    }
