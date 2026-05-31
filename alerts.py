"""
alerts.py - Alim firsati uyarilari (15 dk mantik)
"""
from __future__ import annotations

from config import (
    ALERT_RSI_MAX,
    ALERT_SENTIMENT_MIN,
    BUY_PROB_THRESHOLD,
    RSI_OVERSOLD,
)


def check_buy_opportunity(
    ticker: str,
    ml_result: dict,
    sentiment: dict,
    technical: dict,
) -> dict:
    """
    Guclu alim firsati mi?
    Kosullar: yuksek sentiment + teknik destek + ML olasiligi
    """
    sent_score = sentiment.get("score", 0)
    prob_up = ml_result.get("prob_up", 0.5)
    rsi = technical.get("rsi", 50)
    macd_sig = technical.get("macd_signal", "neutral")
    rec = ml_result.get("recommendation", "BEKLE")

    reasons = []
    score = 0

    if sent_score >= ALERT_SENTIMENT_MIN:
        score += 2
        reasons.append(f"Haber sentiment guclu pozitif ({sent_score:+.2f})")

    if prob_up >= BUY_PROB_THRESHOLD:
        score += 2
        reasons.append(f"ML yukari olasilik %{prob_up*100:.0f}")

    if rsi < ALERT_RSI_MAX and rsi > RSI_OVERSOLD - 10:
        score += 1
        reasons.append(f"RSI destekliyor ({rsi:.1f})")

    if macd_sig == "bullish":
        score += 1
        reasons.append("MACD yukari kesisim")

    if technical.get("close", 0) > technical.get("sma_20", 0):
        score += 1
        reasons.append("Fiyat SMA20 uzerinde")

    is_alert = score >= 4 and rec in ("AL", "BEKLE") and sent_score > 0

    return {
        "ticker": ticker,
        "alert": is_alert,
        "score": score,
        "message": (
            f"ALIM FIRSATI: {ticker} - {' | '.join(reasons)}"
            if is_alert
            else f"{ticker}: normal izleme (skor {score}/7)"
        ),
        "reasons": reasons,
    }
