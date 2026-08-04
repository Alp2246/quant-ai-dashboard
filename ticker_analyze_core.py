"""
ticker_analyze_core.py - Streamlit'siz tam analiz (PC ile ayni Master Score zinciri).

app.py analyze_ticker() ile ayni mantik; sunucu score_job ve testler icin.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from alerts import check_buy_opportunity
from cash_runway import compute_cash_runway
from competitor_benchmark import COMPETITOR_GROUPS
from competitor_benchmark import relative_strength as competitor_rs
from data_fetcher import fetch_history, yearly_performance
from fundamentals import get_fundamental_summary
from master_score import compute_master_score
from ml_model import full_analysis
from moonshot_detector import (
    MOONSHOT_CANDIDATES,
    SECONDARY_MOONSHOT,
    detect_moonshot,
    get_explosive_factor,
)
from moat_analysis import get_moat
from notifications import handle_critical_triggers, handle_master_score
from radar_watchlist import durability_score
from research_agent import get_dynamic_master_coef, get_intensity
from sentiment_analysis import get_ticker_sentiment
from strategic_overlays import get_overlay, is_speculative
from technical_indicators import latest_technical_snapshot
from verdict_rules import verdict_for
from visionary_goals import critical_news_weight, scan_vision

logger = logging.getLogger(__name__)


def _safe(fn, default, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.debug("%s: %s", fn.__name__ if hasattr(fn, "__name__") else fn, exc)
        return default


def analyze_ticker_core(ticker: str, df: pd.DataFrame | None = None) -> dict[str, Any]:
    """PC dashboard ile ayni master score pipeline (Streamlit cache yok)."""
    if df is None or df.empty:
        df = fetch_history(ticker, period="5y")
    if df is None or df.empty:
        return {"ticker": ticker, "error": "no_data"}

    sent = _safe(get_ticker_sentiment, {"score": 50, "news_raw": [], "critical": {}}, ticker)
    fund = _safe(get_fundamental_summary, {"score": 50}, ticker)
    tech = _safe(
        latest_technical_snapshot,
        {"close": 0, "rsi": 50, "atr_pct": 0, "risk_label": "-",
         "stop_loss": 0, "take_profit": 0},
        df,
    )
    ml = _safe(
        full_analysis,
        {"recommendation": "BEKLE", "prob_up": 0.5, "train_samples": 0, "accuracy": 0},
        df, sent.get("score", 50), fund.get("score", 50),
    )

    vision = _safe(scan_vision, None, ticker, sent.get("news_raw", []))
    crit_w = _safe(critical_news_weight, {"weight": 0}, ticker, sent.get("news_raw", []))
    moat = _safe(get_moat, {"innovation_risk": False, "moat_score": 0}, ticker)

    intel = _safe(get_intensity, {"dynamic_coef": 1.0, "intensity": 0}, ticker)
    research_coef = float(intel.get("dynamic_coef", 1.0))
    research_intensity = float(intel.get("intensity", 0))

    sibling_news = None
    tu = ticker.upper()
    if tu == "IONQ":
        s1 = _safe(get_ticker_sentiment, {}, "RGTI").get("news_raw", [])
        s2 = _safe(get_ticker_sentiment, {}, "QBTS").get("news_raw", [])
        sibling_news = (s1 or []) + (s2 or [])
    elif tu == "RGTI":
        s1 = _safe(get_ticker_sentiment, {}, "IONQ").get("news_raw", [])
        s2 = _safe(get_ticker_sentiment, {}, "QBTS").get("news_raw", [])
        sibling_news = (s1 or []) + (s2 or [])
    elif tu == "QBTS":
        s1 = _safe(get_ticker_sentiment, {}, "IONQ").get("news_raw", [])
        s2 = _safe(get_ticker_sentiment, {}, "RGTI").get("news_raw", [])
        sibling_news = (s1 or []) + (s2 or [])

    nvda_news = None
    if tu == "NVTS":
        nvda_news = _safe(get_ticker_sentiment, {}, "NVDA").get("news_raw", [])

    strategic = _safe(
        get_overlay,
        {"overlay_bonus": 0, "labels": [], "details": {}},
        ticker, sent.get("news_raw", []),
        sibling_news=sibling_news, nvda_news=nvda_news,
    )

    runway = {"master_penalty": 0, "is_unsustainable": False, "is_warning": False}
    if is_speculative(ticker):
        runway = _safe(compute_cash_runway, runway, ticker)

    comp_bench = {"bonus": 0}
    if tu in COMPETITOR_GROUPS:
        comp_bench = _safe(competitor_rs, comp_bench, ticker, days=120)

    moonshot = {"master_bonus": 0, "is_moonshot_candidate": False}
    if tu in (MOONSHOT_CANDIDATES | SECONDARY_MOONSHOT):
        moonshot = _safe(detect_moonshot, moonshot, ticker)

    combined_strategic = (
        strategic.get("overlay_bonus", 0) + comp_bench.get("bonus", 0)
    )

    master = _safe(
        compute_master_score,
        {"master_score": 0, "rating": "VERI YOK", "breakdown": {}},
        tech, sent, fund, ml,
        vision=vision,
        critical_weight=crit_w,
        moat=moat,
        research_coef=research_coef,
        research_intensity=research_intensity,
        strategic_overlay_bonus=combined_strategic,
        runway_penalty=runway.get("master_penalty", 0),
        moonshot_bonus=moonshot.get("master_bonus", 0),
    )

    ms = float(master.get("master_score", 0))
    geo = {"critical_alert": False}

    # ---- CARPIMSAL KAPILAR (score_gate.py) --------------------------------
    # compute_master_score'un additive ciktisi KORUNUR; karar ve push bu
    # kapilardan gecen final skora baglanir. Gerekce: LAES'te additive
    # toplam 94.5 "KRITIK ALIM" uretirken ayni pakette SIDDETLI OVERFIT,
    # fiyat<SMA20<SMA50 ve marj -%187 vardi (olculdu 02.08.2026).
    from score_gate import apply_gates
    from verdict_rules import allow_push, gated_verdict

    gates = apply_gates(
        ms,
        technical=tech,
        ml_result=ml,
        fundamental=fund,
        overlay_bonus=master.get("strategic_overlay_bonus", 0),
        moonshot_bonus=master.get("modifiers", {}).get("moonshot", 0),
        base_score=master.get("base_score"),
        pr_only=bool(strategic.get("pr_only")),
        binding=bool(strategic.get("binding_evidence")),
    )

    verdict, gate_reasons = gated_verdict(
        gates["final_score"],
        market_status=gates["market_status"],
        is_overfit=gates["is_overfit"],
        fund_status=gates["fund_status"],
        pr_only=gates["pr_only"],
        cash_unsustainable=bool(runway.get("is_unsustainable")),
        critical_alert=bool(geo.get("critical_alert")),
    )
    push_ok, push_red = allow_push(
        verdict,
        market_status=gates["market_status"],
        is_overfit=gates["is_overfit"],
    )
    gates["reasons"].extend(gate_reasons)
    if push_red:
        gates["reasons"].append(push_red)
    gates["verdict"] = verdict
    gates["allow_push"] = push_ok

    # Additive kirilim panelde gorunmeye devam etsin diye master_score
    # ham haliyle korunur; karar final_score uzerinden verilir.
    master["score_raw"] = gates["score_raw"]
    master["final_score"] = gates["final_score"]
    master["gates"] = gates
    master["rating"] = verdict
    master["verdict"] = verdict

    return {
        "ticker": ticker,
        "df": df,
        "master": master,
        "gates": gates,
        "allow_push": push_ok,
        "sentiment": sent,
        "fundamental": fund,
        "technical": tech,
        "ml": ml,
        "vision": vision,
        "strategic_overlay": strategic,
        "cash_runway": runway,
        "moonshot": moonshot,
        "competitor_benchmark": comp_bench,
        "verdict": verdict,
        "master_score": ms,
    }


def score_summary(ticker: str) -> dict[str, Any]:
    """score_job icin kisa cikti."""
    r = analyze_ticker_core(ticker)
    if r.get("error"):
        return {"ticker": ticker, "error": r["error"]}
    m = r["master"]
    g = r.get("gates") or {}
    return {
        "ticker": ticker,
        # master_score artik KAPILARDAN GECMIS skordur; score_raw additive
        # kirilimi panelde gostermek icin ayrica tasinir.
        "master_score": g.get("final_score", r["master_score"]),
        "score_raw": g.get("score_raw", r["master_score"]),
        "rating": m.get("rating"),
        "verdict": r["verdict"],
        "allow_push": r.get("allow_push", True),
        "gates": {
            "M_market": g.get("M_market"), "M_overfit": g.get("M_overfit"),
            "M_fund": g.get("M_fund"), "market_status": g.get("market_status"),
            "fund_status": g.get("fund_status"), "pr_only": g.get("pr_only"),
            "binding": g.get("binding"), "is_overfit": g.get("is_overfit"),
            "overfit_verdict": g.get("overfit_verdict"),
            "reasons": g.get("reasons", []),
        },
    }
