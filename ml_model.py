"""
ml_model.py - Teknik + sentiment ile yon tahmini (scikit-learn / XGBoost)
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from config import (ML_TEST_RATIO, ML_TRAIN_DAYS, PURGED_CV_EMBARGO_DAYS,
                    PURGED_CV_HORIZON_DAYS, RANDOM_STATE)
from technical_indicators import add_indicators

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "rsi",
    "macd",
    "macd_hist",
    "returns_1d",
    "volatility_20",
    "sma_ratio",        # Close / sma_50
    "atr_pct",          # volatilite olcusu
    "sentiment",        # haber + Reddit sentiment
    "fundamental",      # Fundamental Score 0..100
]


def _prepare_features(
    df: pd.DataFrame,
    sentiment_score: float = 0.0,
    fundamental_score: float = 50.0,
) -> pd.DataFrame:
    """ML icin ozellik matrisi."""
    data = df.copy()
    data["sma_ratio"] = data["Close"] / data["sma_50"].replace(0, np.nan)
    if "atr_pct" not in data.columns:
        data["atr_pct"] = 2.0
    data["sentiment"] = sentiment_score
    data["fundamental"] = fundamental_score
    data["target"] = (data["Close"].shift(-1) > data["Close"]).astype(int)
    data = data.dropna(subset=FEATURE_COLS + ["target"])
    return data


def train_model(
    df: pd.DataFrame,
    sentiment_score: float = 0.0,
    fundamental_score: float = 50.0,
    use_xgboost: bool = True,
) -> dict:
    """
    Model egit ve son tahmin dondur.
    Returns: prob_up, recommendation, accuracy, feature_importance
    """
    data = _prepare_features(df, sentiment_score, fundamental_score)
    if len(data) < 80:
        return _fallback_prediction(df, sentiment_score, reason="yetersiz veri")

    # Son N gun ile sinirla
    if len(data) > ML_TRAIN_DAYS:
        data = data.iloc[-ML_TRAIN_DAYS:]

    X = data[FEATURE_COLS].values
    y = data["target"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=ML_TEST_RATIO, shuffle=False
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    if use_xgboost:
        try:
            from xgboost import XGBClassifier
            model = XGBClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.08,
                random_state=RANDOM_STATE,
                eval_metric="logloss",
                verbosity=0,
            )
        except ImportError:
            model = GradientBoostingClassifier(
                n_estimators=80, max_depth=4, random_state=RANDOM_STATE
            )
    else:
        model = RandomForestClassifier(
            n_estimators=120, max_depth=6, random_state=RANDOM_STATE
        )

    model.fit(X_train_s, y_train)
    acc = accuracy_score(y_test, model.predict(X_test_s)) if len(y_test) > 5 else 0.5

    # ---- LOPEZ DE PRADO PURGED K-FOLD CV (overfit teshisi) ----
    # Bu adim financial ML modellerinin auto-correlated leakage'ini engeller.
    # Train-test arasinda 'horizon' kadar veri purge edilir + 'embargo' bosluk.
    cv_report: dict = {"verdict": "ATLANDI", "overfitting_gap": 0.0,
                          "mean_accuracy": 0.0, "n_folds_used": 0,
                          "per_fold_acc": []}
    try:
        from purged_cv import purged_kfold_cv_score
        # Standardize edilmis tum veri uzerinde 5-fold purged CV
        X_full_s = scaler.transform(X)
        cv_report = purged_kfold_cv_score(
            model, pd.DataFrame(X_full_s, columns=FEATURE_COLS), y,
            n_splits=5,
            horizon_days=PURGED_CV_HORIZON_DAYS,
            embargo_days=PURGED_CV_EMBARGO_DAYS,
        )
    except Exception as e:
        logger.debug("purged_cv atlandi: %s", e)

    # Son bar tahmini
    last_row = _prepare_features(df, sentiment_score, fundamental_score).iloc[-1:]
    X_last = scaler.transform(last_row[FEATURE_COLS].values)
    prob_up = float(model.predict_proba(X_last)[0][1])

    recommendation = _prob_to_signal(prob_up, sentiment_score, df)

    # Feature importance
    if hasattr(model, "feature_importances_"):
        imp = dict(zip(FEATURE_COLS, model.feature_importances_))
    else:
        imp = {}

    return {
        "prob_up": round(prob_up, 4),
        "prob_down": round(1 - prob_up, 4),
        "recommendation": recommendation,
        "accuracy": round(acc, 4),
        "model_type": type(model).__name__,
        "feature_importance": imp,
        "train_samples": len(X_train),
        # Lopez de Prado Purged CV ciktilari
        "cv_mean_accuracy": cv_report.get("mean_accuracy", 0.0),
        "cv_std_accuracy": cv_report.get("std_accuracy", 0.0),
        "overfitting_gap": cv_report.get("overfitting_gap", 0.0),
        "overfit_verdict": cv_report.get("verdict", "ATLANDI"),
        "cv_per_fold": cv_report.get("per_fold_acc", []),
        "cv_n_folds": cv_report.get("n_folds_used", 0),
    }


def _prob_to_signal(prob_up: float, sentiment: float, df: pd.DataFrame) -> str:
    """Al / Bekle / Sat karari."""
    from config import BUY_PROB_THRESHOLD, RSI_OVERBOUGHT, RSI_OVERSOLD, SENTIMENT_BEARISH

    rsi = float(df["rsi"].iloc[-1]) if "rsi" in df.columns and not pd.isna(df["rsi"].iloc[-1]) else 50

    if prob_up >= BUY_PROB_THRESHOLD and sentiment >= -0.05 and rsi < RSI_OVERBOUGHT:
        return "AL"
    if prob_up < 0.40 or sentiment < SENTIMENT_BEARISH or rsi > RSI_OVERBOUGHT:
        return "SAT"
    if rsi < RSI_OVERSOLD and sentiment > 0:
        return "AL"
    return "BEKLE"


def _fallback_prediction(df: pd.DataFrame, sentiment: float, reason: str) -> dict:
    """Model egitilemezse kural tabanli."""
    from technical_indicators import latest_technical_snapshot
    tech = latest_technical_snapshot(df)
    rsi = tech["rsi"]
    score = 0
    if rsi < 40:
        score += 1
    if rsi > 65:
        score -= 1
    if tech["macd_signal"] == "bullish":
        score += 1
    elif tech["macd_signal"] == "bearish":
        score -= 1
    if sentiment > 0.1:
        score += 1
    elif sentiment < -0.1:
        score -= 1

    if score >= 2:
        rec = "AL"
        prob = 0.62
    elif score <= -2:
        rec = "SAT"
        prob = 0.38
    else:
        rec = "BEKLE"
        prob = 0.50

    return {
        "prob_up": prob,
        "prob_down": 1 - prob,
        "recommendation": rec,
        "accuracy": None,
        "model_type": f"rule_based ({reason})",
        "feature_importance": {},
        "train_samples": 0,
        "cv_mean_accuracy": 0.0, "cv_std_accuracy": 0.0,
        "overfitting_gap": 0.0, "overfit_verdict": "FALLBACK",
        "cv_per_fold": [], "cv_n_folds": 0,
    }


def full_analysis(df: pd.DataFrame,
                  sentiment_score: float,
                  fundamental_score: float = 50.0) -> dict:
    return train_model(df, sentiment_score, fundamental_score, use_xgboost=True)
