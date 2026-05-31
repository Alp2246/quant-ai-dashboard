"""
app.py - Quant AI Dashboard v3 (Streamlit)

Sekmeler:
  Ozet | Detay | Backtest | Forecast | Temel | Radar (Watchlist) |
  Milestone | DCA | Loglar

Yeni: Watchlist Manager (sidebar), Risk Dagilim Grafigi, CAGR, Durability Score,
      Milestone Timeline, DCA Calculator, Kritik Teknik Haber (InP/GaAs/SiC).

Calistirma: streamlit run app.py
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from alerts import check_buy_opportunity
from backtest import backtest_strategy
from capex_watch import derive_ticker_capex_weight, scan_sector
from config import ALL_WATCHLIST_DEFAULTS, CHINA_TICKERS, REFRESH_MINUTES, TICKERS
from correlation_matrix import (build_correlation, find_pair_opportunities,
                                 relative_performance)
from data_fetcher import (fetch_all_histories, fetch_history, get_currency,
                           to_usd, yearly_performance)
from dca_calculator import historical_dca, portfolio_dca, projected_dca
from forecasting import forecast_long_term, forecast_prophet
from fundamentals import get_fundamental_summary
from hardware_intel import (cache_age_hours, get_cycle_modifier, get_geo_risk,
                              get_intel, get_macro_bonus, get_patent_bonus,
                              get_production_score, is_stale, run_scan)
from master_score import compute_master_score
from research_agent import (age_hours as research_age_hours,
                              get_cache as get_research_cache,
                              get_dynamic_master_coef, get_intensity,
                              is_stale as research_stale, run_daily_research)
from strategic_overlays import get_overlay, is_speculative
from cash_runway import compute_cash_runway
from investor_summary import build_investor_overview, get_verdict_color
from black_litterman import portfolio_optimization
from competitor_benchmark import relative_strength as competitor_rs, COMPETITOR_GROUPS
from moonshot_detector import (detect_moonshot, MOONSHOT_CANDIDATES,
                                  SECONDARY_MOONSHOT, get_explosive_factor)
from executive_brief import brief_for_ticker, market_summary
from engineering_notes import get_engineering_note
from milestones import get_timeline
from ml_model import full_analysis
from moat_analysis import get_moat
from notifications import (get_log_tail, handle_master_score,
                              handle_critical_triggers)
from radar_watchlist import durability_score, watchlist_analyze
from risk_distribution import build_distribution
from sector_intelligence import derive_sector_weight, scan_all_chains
from sentiment_analysis import get_ticker_sentiment
from technical_indicators import latest_technical_snapshot
from visionary_goals import critical_news_weight, get_vision, scan_vision
from volatility_smile import get_implied_volatility

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Quant AI Dashboard v7 - Deep Research Agent",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def cached_currency(ticker: str) -> str:
    try:
        return get_currency(ticker)
    except Exception:
        return "USD"


def fmt_price(price: float, ticker: str) -> str:
    """Hisse fiyatini para birimiyle birlikte goster."""
    curr = cached_currency(ticker)
    sym = {"USD": "$", "HKD": "HK$", "EUR": "€", "CNY": "¥", "GBP": "£"}.get(curr, "")
    return f"{sym}{price:.2f}" if price else f"{sym}0.00"


def usd_equivalent(price: float, ticker: str) -> str:
    """Yabanci para birimi -> USD karsiligi etiketi."""
    curr = cached_currency(ticker)
    if curr == "USD":
        return ""
    return f" (~${to_usd(price, curr):.2f})"

SIGNAL_COLORS = {"AL": "#00c853", "BEKLE": "#ffc107", "SAT": "#ff1744"}
RATING_COLORS = {
    "KRITIK ALIM": "#d500f9", "GUCLU AL": "#00c853", "AL": "#69f0ae",
    "BEKLE":       "#ffc107", "DIKKAT":   "#ff9100", "SAT": "#ff1744",
}

# Runtime cache (df'leri tutup cache_data ile key paylasimi yapmak icin)
_HIST_CACHE: dict[str, pd.DataFrame] = {}


# ===========================================================================
# Cache wrapper'lar
# ===========================================================================

@st.cache_data(ttl=REFRESH_MINUTES * 60, show_spinner=False)
def cached_history(ticker: str, period: str = "5y"):
    try:
        return fetch_history(ticker, period=period)
    except Exception as e:
        logger.error("history %s: %s", ticker, e)
        return pd.DataFrame()


@st.cache_data(ttl=REFRESH_MINUTES * 60, show_spinner=False)
def cached_all_histories(tickers_tuple: tuple):
    try:
        return fetch_all_histories(list(tickers_tuple))
    except Exception as e:
        logger.error("all_histories: %s", e)
        return {}


@st.cache_data(ttl=REFRESH_MINUTES * 60, show_spinner=False)
def cached_sentiment(ticker: str):
    try:
        return get_ticker_sentiment(ticker)
    except Exception as e:
        logger.error("sentiment %s: %s", ticker, e)
        return {
            "score": 0, "label": "yok", "count": 0, "headlines": [],
            "news_score": 0, "news_count": 0, "news_raw": [],
            "reddit_score": 0, "reddit_count": 0, "reddit_label": "yok",
            "reddit_posts": [],
            "critical": {"total_critical": 0, "categories": [], "examples": {}},
        }


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_fundamentals(ticker: str):
    try:
        return get_fundamental_summary(ticker)
    except Exception as e:
        logger.error("fundamentals %s: %s", ticker, e)
        return {"score": 50, "rating": "VERI YOK", "market_cap_human": "-",
                "sector": "-", "industry": "-", "breakdown": {},
                "revenue_growth_pct": 0, "profit_margin_pct": 0,
                "operating_cashflow": 0, "free_cashflow": 0, "debt_to_equity": 0,
                "forward_pe": 0, "beta": 1.0, "short_ratio": 0,
                "target_mean_price": 0, "current_price": 0, "analyst_upside_pct": 0,
                "market_cap": 0, "revenue": 0}


@st.cache_data(ttl=REFRESH_MINUTES * 60, show_spinner=False)
def cached_backtest(ticker: str, last_date_key: str):
    df = _HIST_CACHE.get(ticker)
    if df is None or df.empty:
        df = cached_history(ticker)
    try:
        return backtest_strategy(df, holding_days=20, years=2)
    except Exception as e:
        logger.error("backtest %s: %s", ticker, e)
        from backtest import _empty_result
        return _empty_result()


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def cached_forecast(ticker: str, last_date_key: str):
    df = _HIST_CACHE.get(ticker)
    if df is None or df.empty:
        df = cached_history(ticker)
    try:
        return forecast_prophet(df, horizon_days=180)
    except Exception as e:
        logger.error("forecast %s: %s", ticker, e)
        return {"model": "hata", "last_actual": 0, "target_price": 0,
                "lower_band": 0, "upper_band": 0, "change_pct": 0,
                "snapshots": {}, "forecast_df": pd.DataFrame(),
                "history": pd.DataFrame()}


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def cached_forecast_long(ticker: str, last_date_key: str,
                          exponential_mode: bool = False):
    df = _HIST_CACHE.get(ticker)
    if df is None or df.empty:
        df = cached_history(ticker, period="10y")
    try:
        return forecast_long_term(df, years=10, ticker=ticker,
                                   exponential_mode=exponential_mode)
    except Exception as e:
        logger.error("forecast_long %s: %s", ticker, e)
        return {"model": "hata", "last_actual": 0, "target_price": 0,
                "lower_band": 0, "upper_band": 0, "change_pct": 0,
                "implied_cagr_pct": 0, "historical_5y_cagr_pct": 0,
                "snapshots": {}, "forecast_df": pd.DataFrame(),
                "history": pd.DataFrame(),
                "cap_value": 0, "floor_value": 0, "cap_multiplier": 0,
                "saturation": {"applied_saturation": False, "warning": None}}


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_durability(ticker: str):
    try:
        return durability_score(ticker)
    except Exception as e:
        logger.error("durability %s: %s", ticker, e)
        return {"durability": 0, "rating": "VERI YOK", "verdict": str(e),
                "breakdown": {}, "raw": {}}


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_watchlist(ticker: str):
    try:
        return watchlist_analyze(ticker)
    except Exception as e:
        logger.error("watchlist %s: %s", ticker, e)
        return None


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_historical_dca(ticker: str, monthly: float, years: int):
    try:
        return historical_dca(ticker, monthly, years)
    except Exception as e:
        logger.error("hist DCA %s: %s", ticker, e)
        return None


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_projected_dca(ticker: str, monthly: float, years: int):
    try:
        return projected_dca(ticker, monthly, years)
    except Exception as e:
        logger.error("proj DCA %s: %s", ticker, e)
        return None


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def cached_moat(ticker: str):
    try:
        return get_moat(ticker)
    except Exception as e:
        logger.error("moat %s: %s", ticker, e)
        return {"rd_pct": 0, "innovation_risk": False, "moat_rating": "VERI YOK",
                "moat_score": 0, "message": str(e), "gross_margin_pct": 0,
                "operating_margin_pct": 0, "rd_dollars_m": 0, "revenue_m": 0,
                "pricing_power": "-"}


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def cached_moonshot(ticker: str):
    """Moonshot J-Curve dedektoru - 6 saat cache."""
    try:
        return detect_moonshot(ticker)
    except Exception as e:
        logger.error("moonshot %s: %s", ticker, e)
        return {"ticker": ticker, "is_moonshot_candidate": False,
                "master_bonus": 0, "j_curve_score": 0,
                "labels": [], "rationale": str(e),
                "revenue_yoy_pct": None, "rd_yoy_pct": None,
                "revenue_multiplier": None, "backlog_growth_pct": None}


@st.cache_data(ttl=60 * 60 * 2, show_spinner=False)
def cached_competitor(ticker: str):
    """Rakip kiyaslama (relative strength) - 2 saat cache."""
    try:
        return competitor_rs(ticker, days=120)
    except Exception as e:
        logger.error("competitor %s: %s", ticker, e)
        return {"bonus": 0, "label": "HATA", "competitors": [],
                "narrative": str(e), "ticker_return_pct": 0,
                "competitor_avg_return_pct": 0, "relative_strength_pp": 0,
                "per_competitor": {}}


@st.cache_data(ttl=60 * 30, show_spinner=False)
def cached_iv(ticker: str):
    try:
        return get_implied_volatility(ticker)
    except Exception as e:
        logger.error("IV %s: %s", ticker, e)
        return {"success": False, "atm_iv_pct": 0, "skew_pp": 0,
                "fear_score": 0, "fear_label": "HATA",
                "spot": 0, "put_iv_pct": 0, "call_iv_pct": 0,
                "nearest_expiry": None, "n_contracts": 0}


@st.cache_data(ttl=60 * 30, show_spinner=False)
def cached_capex_scan():
    """Foundry deviceri (TSMC, Samsung vb.) tum hisseler icin paylasimli."""
    try:
        return scan_sector()
    except Exception as e:
        logger.error("capex scan: %s", e)
        return {}


@st.cache_data(ttl=60 * 30, show_spinner=False)
def cached_sector_chains():
    """Sektorel zincirler - NVDA, TSM, IBM tetikleyici hareketleri."""
    try:
        return scan_all_chains(days=30)
    except Exception as e:
        logger.error("sector chains: %s", e)
        return {}


# ===========================================================================
# Tek hisse analiz fonksiyonu
# ===========================================================================

def analyze_ticker(ticker: str, df: pd.DataFrame) -> dict:
    """Tum cikti zincirini (sentiment->fundamental->tech->ml->master) hesapla."""
    _HIST_CACHE[ticker] = df

    sent = cached_sentiment(ticker)
    fund = cached_fundamentals(ticker)

    try:
        tech = latest_technical_snapshot(df)
    except Exception as e:
        logger.error("technical %s: %s", ticker, e)
        tech = {"close": 0, "rsi": 50, "rsi_signal": "neutral",
                "macd": 0, "macd_signal": "neutral", "macd_hist": 0,
                "sma_20": 0, "sma_50": 0, "atr": 0, "atr_pct": 0,
                "risk_label": "VERI YOK", "stop_loss": 0, "take_profit": 0,
                "stop_pct": 0, "take_pct": 0, "rr_ratio": 0}

    try:
        ml = full_analysis(df, sent["score"], fund.get("score", 50))
    except Exception as e:
        logger.error("ML %s: %s", ticker, e)
        ml = {"recommendation": "BEKLE", "prob_up": 0.5,
              "model_type": "fallback (hata)", "accuracy": 0,
              "feature_importance": {}, "train_samples": 0}

    # Visionary Goals + critical news weight
    try:
        vision = scan_vision(ticker, sent.get("news_raw", []))
    except Exception as e:
        logger.error("vision %s: %s", ticker, e)
        vision = None
    try:
        crit_w = critical_news_weight(ticker, sent.get("news_raw", []))
    except Exception:
        crit_w = {"weight": 0, "context": []}

    # Sektorel Zeka katmanlari
    moat = cached_moat(ticker)
    capex_scan = cached_capex_scan()
    sector_chains = cached_sector_chains()
    try:
        capex_w = derive_ticker_capex_weight(ticker, capex_scan)
    except Exception:
        capex_w = {"capex_weight": 0, "label": "-", "contributors": []}
    try:
        sector_w = derive_sector_weight(ticker, sector_chains)
    except Exception:
        sector_w = {"sector_weight": 0, "label": "-", "chains": []}

    # Volatility (yfinance options - yavas, sadece istek uzerine)
    iv_data = None  # cache miss / pahalı; Detay sekmesinde ayri yuklenecek

    # HIA cache: patent bonus + geo risk + semi cycle + macro bonus
    try:
        patent_bonus = get_patent_bonus(ticker)
    except Exception:
        patent_bonus = 0
    try:
        geo_risk = get_geo_risk(ticker)
    except Exception:
        geo_risk = {"risk_score": 0, "export_weight": 0, "critical_alert": False,
                     "risk_level": "❓ Taranmadi", "negative_items": []}
    try:
        cycle_mod = get_cycle_modifier()
    except Exception:
        cycle_mod = 0
    try:
        macro = get_macro_bonus()
    except Exception:
        macro = 0

    # V7 Research Agent: dinamik Lopez de Prado MDA coef + intensity
    try:
        intel_data = get_intensity(ticker)
        research_coef = float(intel_data.get("dynamic_coef", 1.0))
        research_intensity = float(intel_data.get("intensity", 0))
    except Exception:
        research_coef = 1.0
        research_intensity = 0.0
        intel_data = {"intensity": 0, "net_score": 0, "dynamic_coef": 1.0,
                       "bullish": 0, "bearish": 0, "headlines": []}

    # Stratejik Beklenti overlay (IONQ/RGTI sepet, ATOM lisans, LAES endustriyel)
    sibling_news = None
    heavy_news = None
    tu = ticker.upper()
    if tu == "IONQ":
        try:
            s1 = cached_sentiment("RGTI").get("news_raw", [])
            s2 = cached_sentiment("QBTS").get("news_raw", [])
            sibling_news = (s1 or []) + (s2 or [])
        except Exception:
            sibling_news = []
    elif tu == "RGTI":
        try:
            s1 = cached_sentiment("IONQ").get("news_raw", [])
            s2 = cached_sentiment("QBTS").get("news_raw", [])
            sibling_news = (s1 or []) + (s2 or [])
        except Exception:
            sibling_news = []
    elif tu == "QBTS":
        try:
            s1 = cached_sentiment("IONQ").get("news_raw", [])
            s2 = cached_sentiment("RGTI").get("news_raw", [])
            sibling_news = (s1 or []) + (s2 or [])
        except Exception:
            sibling_news = []
    # LAES (SEALSQ) artik Post-Quantum Hardware Security odakli - heavy
    # industry haber proxy'si kaldirildi.
    nvda_news = None
    if tu == "NVTS":
        try:
            nvda_news = cached_sentiment("NVDA").get("news_raw", [])
        except Exception:
            nvda_news = []

    try:
        strategic = get_overlay(ticker, sent.get("news_raw", []),
                                  sibling_news=sibling_news,
                                  heavy_industry_news=heavy_news,
                                  nvda_news=nvda_news)
    except Exception as e:
        logger.error("strategic overlay %s: %s", ticker, e)
        strategic = {"overlay_bonus": 0, "labels": [], "warnings": [],
                     "details": {}, "evidence": []}

    # Cash Runway (speculative hisseler)
    runway = {"master_penalty": 0, "label": "-", "runway_months": None,
              "is_unsustainable": False}
    if is_speculative(ticker):
        try:
            runway = compute_cash_runway(ticker)
        except Exception as e:
            logger.error("runway %s: %s", ticker, e)

    # Competitor Benchmark (Relative Strength) - kullanici talebi:
    # AXTI vs IQE/Sumitomo, LAES vs Infineon/NXP/STM vb.
    comp_bench = {"bonus": 0, "label": "RAKIP YOK", "competitors": [],
                   "narrative": ""}
    if ticker.upper() in COMPETITOR_GROUPS:
        try:
            comp_bench = cached_competitor(ticker)
        except Exception as e:
            logger.error("competitor benchmark %s: %s", ticker, e)

    # Moonshot J-Curve dedektoru (NVTS, INDI, RGTI + secondary)
    moonshot = {"is_moonshot_candidate": False, "master_bonus": 0,
                  "j_curve_score": 0, "labels": [], "rationale": ""}
    if ticker.upper() in (MOONSHOT_CANDIDATES | SECONDARY_MOONSHOT):
        try:
            moonshot = cached_moonshot(ticker)
        except Exception as e:
            logger.error("moonshot %s: %s", ticker, e)

    # Strategic overlay bonusu + competitor benchmark bonusu toplanir
    combined_strategic_bonus = (strategic.get("overlay_bonus", 0)
                                  + comp_bench.get("bonus", 0))

    try:
        master = compute_master_score(
            tech, sent, fund, ml,
            vision=vision, critical_weight=crit_w,
            sector_weight=sector_w, capex_weight=capex_w,
            fear_level=0, moat=moat,
            patent_bonus=patent_bonus, geo_risk=geo_risk,
            cycle_modifier=cycle_mod,
            macro_bonus=macro,
            research_coef=research_coef,
            research_intensity=research_intensity,
            strategic_overlay_bonus=combined_strategic_bonus,
            runway_penalty=runway.get("master_penalty", 0),
            moonshot_bonus=moonshot.get("master_bonus", 0),
        )
    except Exception as e:
        logger.error("master %s: %s", ticker, e)
        master = {"master_score": 0, "base_score": 0, "vision_bonus": 0,
                  "vision_rating": "-", "critical_weight": 0,
                  "rating": "VERI YOK",
                  "breakdown": {"technical": 0, "sentiment": 0, "fundamental": 0},
                  "components": {}, "confidence_low": 0,
                  "confidence_high": 0, "ml_prob_up": 0.5}

    try:
        handle_master_score(ticker, master["master_score"], master["rating"],
                            details=master["breakdown"])
    except Exception:
        pass

    # Kritik esik tetikleyici notification (v8 eksiklik #3)
    # NVTS Tier-1 OEM, LAES NIST PQC, ATOM JDA, AXTI Ga ihracat kontrolu vb.
    triggered = []
    try:
        # Result dict'i bir araya getir (handler kullanir)
        provisional = {
            "strategic_overlay": strategic,
            "atom_exponential_mode": bool(
                strategic.get("details", {}).get("exponential_mode", False)),
            "geo_risk": geo_risk,
            "ml": ml,
        }
        triggered = handle_critical_triggers(ticker, provisional)
    except Exception as e:
        logger.debug("trigger handler %s: %s", ticker, e)

    try:
        alert = check_buy_opportunity(ticker, ml, sent, tech)
    except Exception:
        alert = {"is_alert": False, "ticker": ticker}

    try:
        yearly = yearly_performance(df)
    except Exception:
        yearly = pd.DataFrame()

    durab = cached_durability(ticker)

    return {
        "ticker": ticker, "df": df, "sentiment": sent,
        "fundamental": fund, "technical": tech, "ml": ml,
        "master": master, "alert": alert, "yearly": yearly,
        "durability_score": durab,
        "vision": vision, "critical_weight": crit_w,
        "moat": moat, "capex_weight": capex_w, "sector_weight": sector_w,
        "iv": iv_data,
        "patent_bonus": patent_bonus, "geo_risk": geo_risk,
        "cycle_modifier": cycle_mod, "macro_bonus": macro,
        "research_coef": research_coef, "research_intensity": research_intensity,
        "research_data": intel_data,
        "strategic_overlay": strategic,
        "competitor_benchmark": comp_bench,
        "moonshot": moonshot,
        "explosive_factor": get_explosive_factor(ticker),
        "cash_runway": runway,
        "atom_exponential_mode": bool(
            strategic.get("details", {}).get("exponential_mode", False)),
        "triggered_events": triggered,
    }


# ===========================================================================
# Grafikler
# ===========================================================================

def plot_price_yearly(df: pd.DataFrame, ticker: str, tech: dict) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.06, row_heights=[0.65, 0.35],
                        subplot_titles=(f"{ticker} - Fiyat", "RSI"))
    fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Kapanis",
                              line=dict(color="#42a5f5", width=2),
                              fill="tozeroy",
                              fillcolor="rgba(66,165,245,0.10)"), row=1, col=1)
    if "sma_20" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["sma_20"], name="SMA20",
                                  line=dict(color="#ffca28", width=1, dash="dot")), row=1, col=1)
    if "sma_50" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["sma_50"], name="SMA50",
                                  line=dict(color="#ab47bc", width=1, dash="dash")), row=1, col=1)
    if tech.get("stop_loss") and tech.get("take_profit"):
        fig.add_hline(y=tech["stop_loss"], line_color="#ff1744", line_dash="dot",
                      row=1, col=1, annotation_text=f"SL ${tech['stop_loss']}",
                      annotation_position="right")
        fig.add_hline(y=tech["take_profit"], line_color="#00c853", line_dash="dot",
                      row=1, col=1, annotation_text=f"TP ${tech['take_profit']}",
                      annotation_position="right")
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI",
                                  line=dict(color="#66bb6a", width=1.5)), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=2, col=1)
    fig.update_layout(height=440, template="plotly_dark",
                      margin=dict(l=40, r=20, t=50, b=30),
                      legend=dict(orientation="h", y=1.12),
                      paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24")
    return fig


def plot_yearly_bars(yearly: pd.DataFrame, ticker: str) -> go.Figure:
    colors = ["#00c853" if r >= 0 else "#ff1744" for r in yearly["return_pct"]]
    fig = go.Figure(go.Bar(x=yearly["year"].astype(str), y=yearly["return_pct"],
                            marker_color=colors,
                            text=[f"{r:+.1f}%" for r in yearly["return_pct"]],
                            textposition="outside"))
    fig.update_layout(title=f"{ticker} - Yillik Getiri %",
                      template="plotly_dark", height=260,
                      paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                      margin=dict(l=40, r=20, t=40, b=20))
    return fig


def plot_macd(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD",
                              line=dict(color="#42a5f5")))
    fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Signal",
                              line=dict(color="#ff7043")))
    colors = ["#00c853" if v >= 0 else "#ff1744" for v in df["macd_hist"].fillna(0)]
    fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"], name="Hist",
                         marker_color=colors, opacity=0.55))
    fig.update_layout(title="MACD", template="plotly_dark", height=220,
                      paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                      margin=dict(l=40, r=20, t=40, b=20))
    return fig


def plot_forecast(fc: dict, ticker: str) -> go.Figure:
    fig = go.Figure()
    hist = fc.get("history", pd.DataFrame()).copy()
    fdf = fc.get("forecast_df", pd.DataFrame()).copy()
    # tz-naive sigortasi (Plotly + pandas comparison icin sart)
    def _strip_tz(df):
        if df.empty or "ds" not in df.columns:
            return df
        df["ds"] = pd.to_datetime(df["ds"], errors="coerce")
        if getattr(df["ds"].dt, "tz", None) is not None:
            df["ds"] = df["ds"].dt.tz_localize(None)
        return df
    hist = _strip_tz(hist)
    fdf = _strip_tz(fdf)
    if not hist.empty:
        fig.add_trace(go.Scatter(x=hist["ds"], y=hist["y"], name="Gecmis",
                                  line=dict(color="#42a5f5", width=2)))
    if not fdf.empty:
        last_hist = hist["ds"].iloc[-1] if not hist.empty else fdf["ds"].iloc[0]
        future = fdf[fdf["ds"] > last_hist]
        fig.add_trace(go.Scatter(x=future["ds"], y=future["yhat_upper"],
                                  line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=future["ds"], y=future["yhat_lower"],
                                  fill="tonexty", fillcolor="rgba(0,200,83,0.18)",
                                  line=dict(width=0),
                                  name="Guven Araligi (%80)"))
        fig.add_trace(go.Scatter(x=future["ds"], y=future["yhat"], name="Tahmin",
                                  line=dict(color="#ffeb3b", width=2, dash="dot")))
    # Logistic cap çizgisi (10y forecast'lar icin)
    cap_v = fc.get("cap_value", 0)
    floor_v = fc.get("floor_value", 0)
    if cap_v and cap_v > 0:
        fig.add_hline(y=cap_v, line_dash="dash", line_color="#ff5252",
                      annotation_text=f"Cap (10y tavan): ${cap_v:,.2f}",
                      annotation_position="top left",
                      annotation_font_color="#ff5252")
    if floor_v and floor_v > 0 and floor_v < cap_v:
        fig.add_hline(y=floor_v, line_dash="dot", line_color="#90a4ae",
                      annotation_text=f"Floor: ${floor_v:,.2f}",
                      annotation_position="bottom left",
                      annotation_font_color="#90a4ae")
    fig.update_layout(title=f"{ticker} - Tahmin ({fc.get('model', '-')})",
                      template="plotly_dark", height=420,
                      paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                      legend=dict(orientation="h", y=1.10))
    return fig


def plot_backtest_equity(bt: dict, ticker: str) -> go.Figure:
    fig = go.Figure()
    if bt["n_trades"] == 0:
        fig.add_annotation(text="Yeterli sinyal yok",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color="white", size=14))
    else:
        trades = bt["trades_df"].copy()
        trades["cum_pct"] = ((1 + trades["return_pct"] / 100).cumprod() - 1) * 100
        fig.add_trace(go.Scatter(x=trades["exit_date"], y=trades["cum_pct"],
                                  mode="lines+markers",
                                  line=dict(color="#00c853", width=2),
                                  marker=dict(size=8), name="Strateji"))
        fig.add_hline(y=bt["buy_hold_return"], line_dash="dash",
                      line_color="#42a5f5",
                      annotation_text=f"Buy&Hold {bt['buy_hold_return']:+.1f}%",
                      annotation_position="right")
    fig.update_layout(title=f"{ticker} - Birikimli Strateji Getirisi",
                      template="plotly_dark", height=320,
                      paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                      yaxis_title="Birikimli %")
    return fig


def plot_master_gauge(master: dict, ticker: str) -> go.Figure:
    sc = master["master_score"]
    color = RATING_COLORS.get(master["rating"], "#888")
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=sc,
        title={"text": f"<b>{ticker}</b><br><span style='font-size:0.7em'>{master['rating']}</span>"},
        delta={"reference": 50, "increasing": {"color": "#00c853"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "white"},
            "bar": {"color": color, "thickness": 0.35},
            "steps": [
                {"range": [0, 25], "color": "#3a0c0c"},
                {"range": [25, 40], "color": "#5a2c0c"},
                {"range": [40, 55], "color": "#5a5a0c"},
                {"range": [55, 70], "color": "#2d5a2d"},
                {"range": [70, 85], "color": "#0c5a3a"},
                {"range": [85, 100], "color": "#5a0c5a"},
            ],
            "threshold": {"line": {"color": "white", "width": 3},
                          "thickness": 0.85, "value": 85},
        }))
    fig.update_layout(height=260, paper_bgcolor="#0e1117",
                      font=dict(color="white"),
                      margin=dict(l=10, r=10, t=40, b=10))
    return fig


def plot_risk_distribution(risk_df: pd.DataFrame) -> go.Figure:
    """10y bust / stable / 10x / 100x dagilim stacked bar."""
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Batma Riski",  x=risk_df["ticker"], y=risk_df["p_bust"],
                          marker_color="#ff1744",
                          text=[f"{v}%" for v in risk_df["p_bust"]], textposition="inside"))
    fig.add_trace(go.Bar(name="Stabil",       x=risk_df["ticker"], y=risk_df["p_stable"],
                          marker_color="#90a4ae",
                          text=[f"{v}%" for v in risk_df["p_stable"]], textposition="inside"))
    fig.add_trace(go.Bar(name="10x Potansiyel", x=risk_df["ticker"], y=risk_df["p_10x"],
                          marker_color="#00c853",
                          text=[f"{v}%" for v in risk_df["p_10x"]], textposition="inside"))
    fig.add_trace(go.Bar(name="100x Spekulatif", x=risk_df["ticker"], y=risk_df["p_100x"],
                          marker_color="#d500f9",
                          text=[f"{v}%" for v in risk_df["p_100x"]], textposition="inside"))
    fig.update_layout(barmode="stack",
                      title="📡 10 Yillik Risk Dagilim Haritasi",
                      template="plotly_dark", height=380,
                      paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                      yaxis_title="Olasilik %",
                      legend=dict(orientation="h", y=-0.15))
    return fig


def plot_timeline(timeline_df: pd.DataFrame, ticker: str) -> go.Figure:
    """Milestone zaman cizelgesi."""
    if timeline_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Milestone bulunamadi", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False,
                           font=dict(color="white", size=14))
        fig.update_layout(height=260, template="plotly_dark",
                          paper_bgcolor="#0e1117")
        return fig
    df = timeline_df.copy()
    df["y"] = range(len(df))
    df["color"] = df["source"].map({"DB": "#42a5f5", "Haber": "#ffeb3b"}).fillna("#888")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["y"], mode="markers+text",
        marker=dict(size=18, color=df["color"], line=dict(color="white", width=1)),
        text=df["event"].str[:60], textposition="middle right",
        textfont=dict(color="white", size=11),
        hovertext=df.apply(lambda r: f"{r['date'].strftime('%Y-%m-%d')}<br>{r['tag']}<br>{r['event']}", axis=1),
        hoverinfo="text",
    ))
    # Bugun cizgisi - pandas/plotly versiyon sorunlarini onlemek icin string olarak
    today_str = pd.Timestamp.today().normalize().strftime("%Y-%m-%d")
    try:
        fig.add_vline(x=today_str, line_dash="dash", line_color="#ff1744",
                       annotation_text="Bugun", annotation_position="top")
    except Exception:
        pass  # plotly versiyonu vline'i kaldirmazsa sessizce gec
    fig.update_layout(title=f"📅 {ticker} - Milestone Zaman Cizelgesi",
                      template="plotly_dark", height=max(260, 60 * len(df) + 100),
                      paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                      showlegend=False, yaxis=dict(visible=False),
                      margin=dict(l=20, r=20, t=50, b=30))
    return fig


def plot_dca_growth(timeline_df: pd.DataFrame, ticker: str) -> go.Figure:
    """Tarihsel DCA grafigi: yatirim vs deger."""
    fig = go.Figure()
    if timeline_df.empty:
        fig.add_annotation(text="Veri yok", x=0.5, y=0.5,
                           xref="paper", yref="paper", showarrow=False)
    else:
        fig.add_trace(go.Scatter(x=timeline_df["date"], y=timeline_df["invested"],
                                  name="Yatirilan", line=dict(color="#42a5f5", width=2)))
        fig.add_trace(go.Scatter(x=timeline_df["date"], y=timeline_df["value"],
                                  name="Bakiye", line=dict(color="#00c853", width=2),
                                  fill="tonexty", fillcolor="rgba(0,200,83,0.15)"))
    fig.update_layout(title=f"{ticker} - DCA Buyume", template="plotly_dark",
                      height=320, paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                      yaxis_title="USD",
                      legend=dict(orientation="h", y=1.10))
    return fig


def plot_dca_projection(timeline_df: pd.DataFrame, ticker: str) -> go.Figure:
    """Projeksiyon: down / central / up senaryolari."""
    fig = go.Figure()
    if timeline_df.empty:
        return fig
    fig.add_trace(go.Scatter(x=timeline_df["date"], y=timeline_df["value_up"],
                              name="Iyi senaryo", line=dict(color="#00c853", width=1)))
    fig.add_trace(go.Scatter(x=timeline_df["date"], y=timeline_df["value_down"],
                              name="Kotu senaryo", line=dict(color="#ff1744", width=1),
                              fill="tonexty", fillcolor="rgba(255,193,7,0.12)"))
    fig.add_trace(go.Scatter(x=timeline_df["date"], y=timeline_df["value_central"],
                              name="Beklenen", line=dict(color="#ffeb3b", width=2)))
    fig.add_trace(go.Scatter(x=timeline_df["date"], y=timeline_df["invested"],
                              name="Yatirilan", line=dict(color="#42a5f5", width=2, dash="dot")))
    fig.update_layout(title=f"{ticker} - 10 Yil DCA Projeksiyonu",
                      template="plotly_dark", height=340,
                      paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                      yaxis_title="USD",
                      legend=dict(orientation="h", y=1.10))
    return fig


# ===========================================================================
# Sekme render'lari
# ===========================================================================

def render_critical_alerts_banner():
    """Son 24 saatte tetiklenmis KRITIK + UYARI olaylari kirmizi banner'da goster."""
    try:
        from notifications import get_recent_critical_events
        events = get_recent_critical_events(hours=24)
    except Exception as e:
        st.caption(f"(Banner yuklenemedi: {e})")
        return

    if not events:
        return

    n_critical = sum(1 for e in events if e["severity"] == "KRITIK")
    n_warning = sum(1 for e in events if e["severity"] == "UYARI")

    # CSS animation
    st.markdown("""
        <style>
        @keyframes pulse_red {
            0%   { box-shadow: 0 0 0 0 rgba(255, 23, 68, 0.7); }
            70%  { box-shadow: 0 0 0 15px rgba(255, 23, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(255, 23, 68, 0); }
        }
        .critical-banner {
            background: linear-gradient(90deg, #b71c1c, #d50000, #ff1744);
            color: #fff !important;
            padding: 14px 18px;
            border-radius: 10px;
            border: 2px solid #ff5252;
            margin-bottom: 14px;
            animation: pulse_red 2.2s infinite;
        }
        .critical-banner h3 { color: #fff !important; margin: 0; }
        .critical-banner p  { color: #fff !important; margin: 4px 0 0 0;
                                font-size: 0.92rem; }
        .critical-event {
            background: #2a0d0d;
            border-left: 4px solid #ff1744;
            padding: 10px 14px;
            border-radius: 6px;
            margin: 6px 0;
            color: #ffd0d0;
        }
        .critical-event b { color: #ffeb3b; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown(
        f"""<div class='critical-banner'>
            <h3>🚨 KRİTİK UYARILAR — Son 24 Saat</h3>
            <p>{n_critical} KRİTİK · {n_warning} UYARI · toplam {len(events)} olay</p>
        </div>""",
        unsafe_allow_html=True,
    )

    # Her olay icin detay
    for ev in events[:10]:  # ilk 10 olayi goster
        sev_emoji = {"KRITIK": "🔴", "UYARI": "🟠"}.get(ev["severity"], "⚪")
        tg_tag = "📲 Telegram'a gonderildi" if ev.get("telegram_sent") else ""
        st.markdown(
            f"""<div class='critical-event'>
                <b>{sev_emoji} {ev['title']}</b><br>
                <span style='color:#ffab91'>Hisse:</span> <b>{ev['ticker']}</b>
                &nbsp;·&nbsp; <span style='color:#ffab91'>{ev['hours_ago']:.1f} saat once</span>
                &nbsp;·&nbsp; <span style='color:#90caf9'>{tg_tag}</span>
                <br><span style='color:#ffe0e0'>{ev['message']}</span>
            </div>""",
            unsafe_allow_html=True,
        )

    if len(events) > 10:
        st.caption(f"... ve {len(events) - 10} kritik olay daha")

    st.markdown("---")


def render_overview(results: dict):
    render_critical_alerts_banner()
    st.markdown("## 🎯 Master Score Tablosu")
    rows = []
    for t, r in results.items():
        m = r["master"]
        tech = r["technical"]
        sent = r["sentiment"]
        v = r.get("vision") or {}
        crit_count = sent.get("critical", {}).get("total_critical", 0)
        rows.append({
            "Hisse": t,
            "Master Score": m["master_score"],
            "Rating": m["rating"],
            "Vision": v.get("vision_bonus", 0),
            "Vizyon": v.get("rating", "-"),
            "Fiyat ($)": round(tech["close"], 2),
            "AI Oneri": r["ml"]["recommendation"],
            "ML %": round(r["ml"]["prob_up"] * 100, 1),
            "Sentiment": round(sent["score"], 2),
            "Fundamental": r["fundamental"]["score"],
            "Durability": r["durability_score"].get("durability", 0),
            "Kritik Haber": crit_count,
            "ATR %": tech["atr_pct"],
            "Risk": tech["risk_label"],
            "Stop": f"${tech['stop_loss']}",
            "Target": f"${tech['take_profit']}",
        })
    df = pd.DataFrame(rows).sort_values("Master Score", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True, column_config={
        "Master Score": st.column_config.ProgressColumn(
            "Master Score", min_value=0, max_value=100, format="%d/100"),
        "ML %": st.column_config.ProgressColumn(
            "ML %", min_value=0, max_value=100, format="%.0f%%"),
        "Fundamental": st.column_config.ProgressColumn(
            "Fundamental", min_value=0, max_value=100, format="%d"),
        "Durability": st.column_config.ProgressColumn(
            "Durability", min_value=0, max_value=100, format="%d"),
    })

    # Master gauge'lar
    st.markdown("### Master Score Gostergeleri")
    cols = st.columns(len(results))
    for col, (t, r) in zip(cols, results.items()):
        with col:
            st.plotly_chart(plot_master_gauge(r["master"], t),
                            use_container_width=True, key=f"ov_gauge_{t}")

    # Risk Dagilim Haritasi
    st.markdown("---")
    st.markdown("### 📡 Risk Dagilim Haritasi (10 Yil)")
    try:
        risk_df = build_distribution(results)
        c1, c2 = st.columns([2, 1])
        with c1:
            st.plotly_chart(plot_risk_distribution(risk_df),
                            use_container_width=True, key="risk_dist")
        with c2:
            st.dataframe(risk_df[["ticker", "p_bust", "p_stable", "p_10x", "p_100x", "risk_band"]],
                         use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Risk dagilim hatasi: {e}")

    # Uyarilar
    critical = [t for t, r in results.items() if r["master"]["master_score"] >= 85]
    strong = [t for t, r in results.items() if 70 <= r["master"]["master_score"] < 85]
    if critical:
        st.error("🚨 KRITIK ALIM (Master >= 85): " + ", ".join(critical))
    if strong:
        st.success("✅ Guclu Al (Master >= 70): " + ", ".join(strong))

    # Kritik teknik haberler
    st.markdown("---")
    st.markdown("### 🔬 Kritik Teknik Haberler (InP, GaAs, SiC, Ihracat Kontrolu)")
    any_crit = False
    for t, r in results.items():
        crit = r["sentiment"].get("critical", {})
        cats = crit.get("categories", [])
        if cats:
            any_crit = True
            cat_str = ", ".join([f"{c[0]} ({c[1]})" for c in cats[:6]])
            st.info(f"**{t}** - {cat_str}")
            for h in r["sentiment"].get("news_raw", []):
                if h.get("is_critical") and h.get("critical"):
                    labels = " / ".join(c["label"] for c in h["critical"][:3])
                    st.caption(f"  • [{labels}] {h.get('title', '')[:140]}")
                    break
    if not any_crit:
        st.caption("Su an InP/GaAs/SiC/ihracat kontrolu ile ilgili kritik haber yok.")


def render_detail(results: dict):
    sel = st.selectbox("Hisse sec", list(results.keys()), key="detail_sel")
    if sel not in results:
        return
    r = results[sel]
    ticker = r["ticker"]
    ml = r["ml"]
    sent = r["sentiment"]
    tech = r["technical"]
    fund = r["fundamental"]
    master = r["master"]
    rec = ml["recommendation"]
    rec_color = SIGNAL_COLORS.get(rec, "#888")

    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
    with c1:
        st.markdown(f"### {ticker}")
        st.caption(f"Son fiyat: **{fmt_price(tech['close'], ticker)}**"
                   f"{usd_equivalent(tech['close'], ticker)}"
                   f"  |  Sektor: {fund.get('sector', '-')}")
    with c2:
        st.plotly_chart(plot_master_gauge(master, ticker),
                        use_container_width=True, key=f"d_gauge_{ticker}")
    with c3:
        ci_lo = master["confidence_low"] * 100
        ci_hi = master["confidence_high"] * 100
        st.metric("ML Yukari %", f"{ml['prob_up']*100:.1f}%",
                  help=f"Wilson %95 CI: {ci_lo:.0f}-{ci_hi:.0f}%")
        st.metric("Sentiment", f"{sent['score']:+.2f}", sent["label"])
    with c4:
        risk_emoji = "🔴" if "YUKSEK" in tech["risk_label"] else ("🟡" if "ORTA" in tech["risk_label"] else "🟢")
        st.metric("ATR Volatilite", f"{tech['atr_pct']:.1f}%",
                  f"{risk_emoji} {tech['risk_label']}")
        st.metric("Fundamental", f"{fund['score']}/100", fund["rating"])

    # SL / Oneri / TP
    sl_c1, sl_c2, sl_c3 = st.columns(3)
    with sl_c1:
        st.markdown(f"<div style='background:#ff1744;color:#fff;padding:10px;"
                    f"border-radius:6px;text-align:center'><b>STOP-LOSS</b><br>"
                    f"${tech['stop_loss']}<br>({tech['stop_pct']}% asagi)</div>",
                    unsafe_allow_html=True)
    with sl_c2:
        high_risk = "🔥 YUKSEK RISK" if "YUKSEK" in tech["risk_label"] else ""
        st.markdown(f"<div style='background:{rec_color};color:#000;padding:10px;"
                    f"border-radius:6px;text-align:center'><b>AI ONERI</b><br>"
                    f"{rec} {high_risk}<br>R/R: {tech['rr_ratio']}</div>",
                    unsafe_allow_html=True)
    with sl_c3:
        st.markdown(f"<div style='background:#00c853;color:#000;padding:10px;"
                    f"border-radius:6px;text-align:center'><b>TAKE-PROFIT</b><br>"
                    f"${tech['take_profit']}<br>(+{tech['take_pct']}% yukari)</div>",
                    unsafe_allow_html=True)

    # Master Score Breakdown (yeni 30/30/20/20 + modifier'lar)
    st.markdown("#### Master Score Bilesenleri (30/30/20/20)")
    bd = master["breakdown"]
    mods = master.get("modifiers", {})
    base = master.get("base_score", 0)
    rc = master.get("research_coef", 1.0)
    ri = master.get("research_intensity", 0)
    bs = master.get("base_scaled", base)
    st.caption(f"Taban: **{base}/100**  x  Research Coef **{rc:.2f}** "
               f"(Intensity {ri:.0f})  =  Olcekli Taban **{bs}**  |  "
               f"Sektor: **{mods.get('sector',0):+}**  "
               f"Capex: **{mods.get('capex',0):+}**  "
               f"Kritik: **{mods.get('critical',0):+}**  "
               f"Korku: **{mods.get('fear',0):+}**  "
               f"Inovasyon: **{mods.get('moat',0):+}**  "
               f"|  🛰 Patent: **{mods.get('patent',0):+}**  "
               f"Geo: **{mods.get('geo',0):+}**  "
               f"Cycle: **{mods.get('cycle',0):+}**  "
               f"📊 **Makro: {mods.get('macro',0):+}**  "
               f"🧬 **Stratejik: {mods.get('strategic',0):+}**  "
               f"💵 **Runway: {mods.get('runway',0):+}**  "
               f"=  Master: **{master['master_score']}**")
    bd_df = pd.DataFrame([
        {"Bilesen": "Teknik (Zamanlama)",     "Puan": bd.get("technical", 0),   "Max": 30},
        {"Bilesen": "Vizyon (Strateji)",      "Puan": bd.get("vision", 0),      "Max": 30},
        {"Bilesen": "Temel (Guvenlik)",       "Puan": bd.get("fundamental", 0), "Max": 20},
        {"Bilesen": "Haber+Reddit (Duyarli.)", "Puan": bd.get("sentiment", 0),   "Max": 20},
    ])
    bd_df["Yuzde"] = bd_df["Puan"] / bd_df["Max"] * 100
    fig_bd = px.bar(bd_df, x="Bilesen", y="Yuzde", text="Puan",
                     color="Yuzde", range_y=[0, 100],
                     color_continuous_scale="RdYlGn")
    fig_bd.update_layout(template="plotly_dark", height=240,
                          paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                          showlegend=False, margin=dict(l=20, r=20, t=20, b=20),
                          yaxis_title="Doluluk %")
    st.plotly_chart(fig_bd, use_container_width=True, key=f"d_bd_{ticker}")

    # ---- MUHENDISLIK NOTU (Detail tab'a tasindi - eksiklik #4) ----
    eng = get_engineering_note(ticker, r)
    if eng["base_note"]:
        with st.container(border=True):
            st.markdown(f"#### 🛠️ Muhendislik Notu — `{ticker}`")
            st.caption(eng["base_note"])
            if eng["dynamic_status"]:
                st.markdown("**Anlik Durum:**")
                for ds in eng["dynamic_status"]:
                    st.markdown(f"- {ds}")
            st.info(f"🎯 **Kritik Esik (Haberden Cek):** {eng['critical_threshold']}")

    # ---- ML OVERFIT TEŞHIS PANELI (Lopez de Prado Purged CV - eksiklik #1) ----
    if ml.get("overfit_verdict") and ml["overfit_verdict"] != "ATLANDI":
        cv_acc = ml.get("cv_mean_accuracy", 0) * 100
        gap = ml.get("overfitting_gap", 0)
        verdict = ml["overfit_verdict"]
        if "SIDDETLI" in verdict:
            badge_color = "#d50000"; emoji = "🚨"
        elif "ORTA" in verdict:
            badge_color = "#ff6e40"; emoji = "⚠️"
        elif "DENGELI" in verdict:
            badge_color = "#00c853"; emoji = "✅"
        else:
            badge_color = "#ffc107"; emoji = "🟡"
        st.markdown(
            f"<div style='background:{badge_color};color:white;padding:8px;"
            f"border-radius:6px;margin:6px 0;'>"
            f"<b>{emoji} ML Overfit Teşhisi (Lopez de Prado Purged CV):</b> "
            f"{verdict}  |  CV Accuracy: {cv_acc:.1f}%  |  Train-CV Gap: "
            f"{gap:+.3f}  |  Folds: {ml.get('cv_n_folds',0)}"
            "</div>", unsafe_allow_html=True)
        with st.expander("Purged CV detaylari", expanded=False):
            st.caption(
                "Lopez de Prado, *Advances in Financial ML* Ch.7 - "
                "Standart k-fold finansal veride leak yapar (auto-correlated). "
                "Purged K-Fold: train-test arasinda horizon kadar 'purge' + "
                "embargo bosluk. Gap > 0.15 = siddetli overfit, model guvensiz."
            )
            folds = ml.get("cv_per_fold", [])
            if folds:
                st.write({f"Fold {i+1}": f"{a*100:.1f}%"
                            for i, a in enumerate(folds)})

    # Sektorel uyarilar
    moat = r.get("moat", {})
    if moat.get("innovation_risk"):
        st.warning(f"⚠️ **Inovasyon Riski**: {moat.get('message','')}")
    capex_w = r.get("capex_weight", {})
    if abs(capex_w.get("capex_weight", 0)) >= 1:
        st.info(f"**Capex Watch:** {capex_w.get('label','-')} "
                f"({capex_w.get('capex_weight',0):+} puan)")
    sector_w = r.get("sector_weight", {})
    if abs(sector_w.get("sector_weight", 0)) >= 1:
        st.info(f"**Sektorel Zincir:** {sector_w.get('label','-')} "
                f"({sector_w.get('sector_weight',0):+} puan)")

    # Grafikler
    g1, g2 = st.columns([2, 1])
    with g1:
        st.plotly_chart(plot_price_yearly(r["df"], ticker, tech),
                        use_container_width=True, key=f"d_price_{ticker}")
    with g2:
        if not r["yearly"].empty:
            st.plotly_chart(plot_yearly_bars(r["yearly"], ticker),
                            use_container_width=True, key=f"d_year_{ticker}")
        st.plotly_chart(plot_macd(r["df"].tail(140)),
                        use_container_width=True, key=f"d_macd_{ticker}")

    # Haberler + Reddit + Kritik
    h1, h2 = st.columns(2)
    with h1:
        st.markdown("#### Son Haberler")
        for h in sent.get("headlines", [])[:5]:
            emoji = "📈" if h["sentiment"] > 0.1 else ("📉" if h["sentiment"] < -0.1 else "➖")
            crit_badge = " 🔥KRITIK" if h.get("is_critical") else ""
            st.caption(f"{emoji} **{h['sentiment']:+.2f}**{crit_badge} — {h.get('title', '')[:90]}")
    with h2:
        st.markdown("#### Reddit Sosyal Medya")
        st.caption(f"Skor: **{sent['reddit_score']:+.2f}** ({sent['reddit_label']}, "
                   f"{sent['reddit_count']} post)")
        for p in sent.get("reddit_posts", [])[:5]:
            emoji = "🚀" if p["sentiment"] > 0.1 else ("👎" if p["sentiment"] < -0.1 else "💬")
            st.caption(f"{emoji} **{p['sentiment']:+.2f}** [{p['source']}] — {p['title'][:85]}")

    # =====================================================================
    # CALCULATION TRACE — Master Score formul izlemi (Math_Specs.md Bolum 1)
    # =====================================================================
    with st.expander("🧮 Hesaplama İzlemi (Calculation Trace) — Master Score formülü",
                       expanded=False):
        st.caption("Bu hisse için anlık Master Score'un nasıl üretildiğinin "
                    "tam dökümü. Math_Specs.md Bölüm 1 ile uyumlu.")
        bd = master.get("breakdown", {})
        mods = master.get("modifiers", {})
        T = bd.get("technical", 0); V = bd.get("vision", 0)
        F = bd.get("fundamental", 0); S = bd.get("sentiment", 0)
        B = T + V + F + S
        kappa = master.get("research_coef", 1.0)
        B_scaled = B * kappa
        M = sum(mods.values())

        st.latex(r"\text{Master\_Score} = \mathrm{clip}_{[0,100]}\big(\, B \cdot \kappa \;+\; M \,\big)")
        st.markdown(f"**Taban skor `B`** (4 ana faktör, 0-100):")
        st.code(
            f"B  =  T({T:>4.1f})  +  V({V:>4.1f})  +  F({F:>4.1f})  +  S({S:>4.1f})  =  {B:>5.1f}",
            language=None)
        st.markdown(f"**Research-Agent dinamik katsayısı `κ`** "
                     f"(Lopez de Prado MDA, [0.5, 1.5]):")
        st.code(f"κ  =  {kappa:.3f}     →    B · κ  =  {B_scaled:.2f}", language=None)

        st.markdown("**Modifier toplamı `M`** (sektör + makro + stratejik + jeo):")
        mod_lines = []
        for k, v in mods.items():
            if v == 0:
                continue
            sign = "+" if v > 0 else ""
            mod_lines.append(f"  {k:<10s}  {sign}{v}")
        if mod_lines:
            st.code("\n".join(mod_lines) + f"\n  {'─'*22}\n  Σ M       {M:+d}",
                    language=None)
        else:
            st.code(f"  Σ M  =  {M:+d}", language=None)

        final = master.get("master_score", 0)
        rating = master.get("rating", "-")
        st.markdown("**Sonuç:**")
        st.code(
            f"Final  =  clip[0,100]( B·κ + M )  =  "
            f"clip[0,100]( {B_scaled:.2f} {M:+d} )  =  {final:.1f}\n"
            f"Rating →  {rating}",
            language=None)
        ci = master.get("ml_confidence_interval")
        if ci and isinstance(ci, (list, tuple)) and len(ci) == 2:
            st.caption(f"ML Olasılık güven aralığı (Wilson 95%): "
                        f"[{ci[0]:.2f}, {ci[1]:.2f}]")

    # =====================================================================
    # MONTE CARLO (GBM) — 10K path, 10Y, VaR + Gaussian
    # =====================================================================
    with st.expander("🎲 Monte Carlo (GBM 10.000 senaryo, 10 yıl)",
                       expanded=False):
        st.caption("Geometric Brownian Motion ile 10.000 farklı 10-yıllık "
                    "evren simüle edilir. Enflasyon, faiz, semi cycle "
                    "stress overlay'i kabul eder. Math_Specs.md Bölüm 4.")
        try:
            import monte_carlo as mc
            cm1, cm2, cm3 = st.columns(3)
            with cm1:
                infl = st.slider("Enflasyon %", 0.0, 12.0, 3.0, 0.5,
                                  key=f"mc_infl_{ticker}") / 100.0
            with cm2:
                rate_hike = st.slider("Faiz şoku %", 0.0, 8.0, 0.0, 0.25,
                                       key=f"mc_rate_{ticker}") / 100.0
            with cm3:
                cycle_choice = st.selectbox(
                    "Semi Cycle Phase",
                    ["EXPANSION", "PEAK", "RECOVERY", "TROUGH", "DOWNTURN"],
                    index=0, key=f"mc_cycle_{ticker}")
            run_mc = st.button(f"▶️ 10.000 path simüle et ({ticker})",
                                 key=f"mc_run_{ticker}")
            if run_mc:
                with st.spinner("10.000 path GBM hesaplanıyor..."):
                    res = mc.run_simulation(
                        ticker=ticker,
                        spot_price=float(r["df"]["Close"].iloc[-1]),
                        horizon_years=10.0, n_paths=10_000,
                        macro_stress={
                            "inflation": infl,
                            "rate_hike": rate_hike,
                            "cycle_phase": cycle_choice,
                        })
                s = res.stats
                # Metrikler
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Median 10Y", f"${s['median_T']:.2f}",
                           f"%{s['cagr_median_pct']:+.1f}/yıl")
                k2.metric("VaR 5% (En Kötü)", f"${s['VaR_5_price']:.2f}",
                           f"{s['VaR_5_pct']:+.1f}%")
                k3.metric("P(bust)", f"%{s['p_bust']:.1f}",
                           "S₀ × 0.20 altı")
                k4.metric("P(10x)", f"%{s['p_10x']:.1f}",
                           f"P(2x)=%{s['p_double']:.1f}")
                # Gaussian / Histogram
                import plotly.graph_objects as go
                fig_mc = go.Figure()
                fig_mc.add_trace(go.Histogram(
                    x=res.terminal_prices,
                    nbinsx=80, name="Terminal fiyat dağılımı",
                    marker_color="#42a5f5", opacity=0.85))
                fig_mc.add_vline(x=s["median_T"], line_color="#ffc107",
                                  annotation_text=f"Median ${s['median_T']:.1f}")
                fig_mc.add_vline(x=s["VaR_5_price"], line_color="#d50000",
                                  annotation_text=f"VaR ${s['VaR_5_price']:.1f}")
                fig_mc.add_vline(x=s["p95"], line_color="#00c853",
                                  annotation_text=f"P95 ${s['p95']:.1f}")
                fig_mc.update_layout(
                    template="plotly_dark", height=380,
                    paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                    title=f"{ticker} — 10Y Terminal Fiyat Dağılımı (Gaussian fit)",
                    xaxis_title="USD", yaxis_title="Path sayısı",
                    showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_mc, use_container_width=True,
                                 key=f"mc_hist_{ticker}")
                st.caption(
                    f"μ_used={s['mu_used']}  σ_used={s['sigma_used']}  |  "
                    f"En Kötü 5: {s['worst_5']}  |  En İyi 5: {s['best_5']}  |  "
                    f"CVaR 5%: %{s['CVaR_5_pct']:+.1f}")
        except Exception as e:
            st.warning(f"Monte Carlo çalıştırılamadı: {e}")

    # =====================================================================
    # MDI / MDA Top-5 — Lopez de Prado Feature Importance
    # =====================================================================
    if ml.get("feature_importance_mdi") or ml.get("feature_importance_mda"):
        with st.expander("🔬 Feature Importance Top-5 (MDI + MDA, Lopez de Prado Ch.8)",
                           expanded=False):
            try:
                import pandas as pd
                from feature_importance import top_features_report
                mdi_df = pd.DataFrame(ml.get("feature_importance_mdi", []) or [])
                mda_df = pd.DataFrame(ml.get("feature_importance_mda", []) or [])
                rep = top_features_report(mdi_df, mda_df, top_n=5)
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**MDI (Breiman 2001 — hızlı, biased)**")
                    if rep["top_mdi"]:
                        df_mdi = pd.DataFrame(rep["top_mdi"])
                        st.dataframe(df_mdi, use_container_width=True,
                                      hide_index=True)
                    else:
                        st.caption("MDI verisi yok.")
                with c2:
                    st.markdown("**MDA (Lopez de Prado — gold standard)**")
                    if rep["top_mda"]:
                        df_mda = pd.DataFrame(rep["top_mda"])
                        st.dataframe(df_mda, use_container_width=True,
                                      hide_index=True)
                    else:
                        st.caption("MDA verisi yok.")
                st.markdown(f"### Verdict: `{rep['verdict']}`")
                st.info(rep["narrative"])
                st.caption(f"Sentiment skoru: {rep['sent_score']}  |  "
                            f"SMA skoru: {rep['sma_score']}  |  "
                            f"Oran (sent/sma): {rep['ratio']}")
            except Exception as e:
                st.caption(f"MDI/MDA panel hatası: {e}")


def render_backtest(results: dict):
    st.markdown("## 📈 Backtest - Son 2 Yil + Triple Barrier")
    st.caption("**Murphy Trend Takip** (RSI 50 yukari kesisim + MACD hist crossover) "
               "+ **Lopez de Prado Triple Barrier** "
               "(SL=2×ATR, TP=3×ATR, 20-gun zaman bariyeri)  |  "
               "Sharpe, MaxDD, Calmar dahil")

    bts = {t: cached_backtest(t, str(r["df"].index[-1])[:10]) for t, r in results.items()}
    total_trades = sum(bt["n_trades"] for bt in bts.values())
    avg_wr = sum(bt["win_rate"] for bt in bts.values()) / max(1, len(bts))
    avg_cum = sum(bt["cum_return"] for bt in bts.values()) / max(1, len(bts))
    avg_bh = sum(bt["buy_hold_return"] for bt in bts.values()) / max(1, len(bts))
    avg_sharpe = sum(bt["sharpe_ratio"] for bt in bts.values()) / max(1, len(bts))
    avg_mdd = sum(bt["max_drawdown_pct"] for bt in bts.values()) / max(1, len(bts))

    st.markdown("### 📊 Toplam Performans")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Toplam Sinyal", total_trades)
    m2.metric("Ortalama Win Rate", f"{avg_wr:.1f}%")
    m3.metric("Ortalama Cum Return", f"{avg_cum:+.1f}%",
              f"{avg_cum - avg_bh:+.1f}% vs B&H")
    m4.metric("Ortalama Sharpe", f"{avg_sharpe:.2f}",
              "1+ iyi, 2+ harika")
    m5.metric("Ortalama Max DD", f"{avg_mdd:.1f}%",
              "yakin 0 = saglam")

    rows = []
    for t, bt in bts.items():
        rows.append({
            "Hisse": t, "Sinyal": bt["n_trades"],
            "Win Rate %": bt["win_rate"],
            "Cum Strateji %": bt["cum_return"],
            "Buy&Hold %": bt["buy_hold_return"],
            "Alpha %": bt["alpha_vs_bh"],
            "Sharpe": bt["sharpe_ratio"],
            "Max DD %": bt["max_drawdown_pct"],
            "B&H DD %": bt["buy_hold_drawdown_pct"],
            "Calmar": bt["calmar_ratio"],
            "Avg Tutma (gun)": bt["avg_holding_days"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                 column_config={
                     "Win Rate %": st.column_config.ProgressColumn(
                         "Win Rate %", min_value=0, max_value=100, format="%.1f%%"),
                 })

    st.info("**Sharpe Ratio** > 1.0 = makul, > 2.0 = mukemmel. "
            "**Max Drawdown**: strateji bilanco zirvesinden inilen en derin dip "
            "(0'a yakin daha saglam). **Calmar** = cum_return / |max_dd|.")

    st.markdown("### Hisse Detayli")
    tabs = st.tabs(list(results.keys()))
    for tab, t in zip(tabs, results.keys()):
        with tab:
            bt = bts[t]
            c1, c2 = st.columns([2, 1])
            with c1:
                st.plotly_chart(plot_backtest_equity(bt, t),
                                use_container_width=True, key=f"bt_eq_{t}")
            with c2:
                st.metric("Sinyal", bt["n_trades"])
                st.metric("Win Rate", f"{bt['win_rate']:.1f}%")
                st.metric("Cum Return", f"{bt['cum_return']:+.1f}%",
                          f"{bt['alpha_vs_bh']:+.1f}% vs B&H")
                st.metric("Sharpe Ratio", f"{bt['sharpe_ratio']:.2f}")
                st.metric("Max Drawdown", f"{bt['max_drawdown_pct']:.1f}%",
                          f"B&H: {bt['buy_hold_drawdown_pct']:.1f}%")
                st.metric("Calmar Ratio", f"{bt['calmar_ratio']:.2f}")
            # Triple Barrier exit distribution
            ec = bt.get("exit_counts", {})
            if any(ec.values()):
                st.markdown("**Triple Barrier Exit Dagilimi:**")
                ec_cols = st.columns(5)
                for i, (k, label) in enumerate([("TP", "🎯 Take-Profit"),
                                                ("SL", "🛑 Stop-Loss"),
                                                ("TIME", "⏱️ Zaman"),
                                                ("SAT", "📉 SAT Sinyali"),
                                                ("END", "🏁 Bitis")]):
                    ec_cols[i].metric(label, ec.get(k, 0))

            if not bt["trades_df"].empty:
                df_t = bt["trades_df"].tail(20).copy()
                # exit_reason'a gore renklendir
                def _color_row(row):
                    color = {"TP": "background-color: #1b5e20",
                             "SL": "background-color: #b71c1c",
                             "TIME": "background-color: #4a4a00",
                             "SAT": "background-color: #4a148c"}.get(
                        row.get("exit_reason"), "")
                    return [color] * len(row)
                try:
                    st.dataframe(df_t.style.apply(_color_row, axis=1),
                                 use_container_width=True, hide_index=True)
                except Exception:
                    st.dataframe(df_t, use_container_width=True, hide_index=True)


def render_forecast(results: dict):
    st.markdown("## 🔮 Fiyat Tahmini (Prophet)")
    horizon = st.radio("Vade", ["6 Ay", "10 Yil"], horizontal=True, key="fc_horizon")

    tabs = st.tabs(list(results.keys()))
    for tab, t in zip(tabs, results.keys()):
        with tab:
            r = results[t]
            if horizon == "6 Ay":
                with st.spinner(f"{t} 6-aylik Prophet egitiliyor..."):
                    fc = cached_forecast(t, str(r["df"].index[-1])[:10])
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.plotly_chart(plot_forecast(fc, t),
                                    use_container_width=True, key=f"fc_6m_{t}")
                with c2:
                    st.metric("Su an", fmt_price(fc.get("last_actual", 0), t))
                    for d in ("30d", "90d", "180d"):
                        if d in fc.get("snapshots", {}):
                            s = fc["snapshots"][d]
                            st.metric(d, fmt_price(s["price"], t),
                                      f"{s['change_pct']:+.1f}%")
            else:
                exp_mode = bool(r.get("atom_exponential_mode", False))
                spin = ("10-yillik Prophet (logistic + EXPONENTIAL)..."
                        if exp_mode else
                        "10-yillik Prophet (logistic + cap)...")
                with st.spinner(f"{t} {spin}"):
                    fc = cached_forecast_long(
                        t, str(r["df"].index[-1])[:10],
                        exponential_mode=exp_mode)
                if exp_mode:
                    st.success("📈 ATOM EXPONENTIAL MOD: Foundry/MST production "
                                "line entegrasyonu tespit edildi - CAGR "
                                "projeksiyonu agresif modda.")

                # Saturation uyarisi (TAM %50 esigi)
                sat = fc.get("saturation", {}) or {}
                if sat.get("applied_saturation"):
                    st.error(sat.get("warning", "Market Cap Saturation revize uygulandi."))
                elif sat.get("warning"):
                    st.info(sat["warning"])

                c1, c2 = st.columns([2, 1])
                with c1:
                    st.plotly_chart(plot_forecast(fc, t),
                                    use_container_width=True, key=f"fc_10y_{t}")
                with c2:
                    st.metric("Su an", fmt_price(fc.get("last_actual", 0), t))
                    cap_v = fc.get("cap_value", 0)
                    cap_m = fc.get("cap_multiplier", 0)
                    if cap_v:
                        st.metric("Cap (10y Tavan)", fmt_price(cap_v, t),
                                   f"{cap_m:.0f}x mevcut fiyat",
                                   help="Prophet 'logistic growth' cap. "
                                         "Tahmin bu seviyeyi asamaz.")
                    st.metric("Tarihsel 5y CAGR",
                              f"{fc.get('historical_5y_cagr_pct', 0):.1f}%")
                    st.metric("Modelin Bekledigi CAGR",
                              f"{fc.get('implied_cagr_pct', 0):.1f}%")

                    # Reality Check - hangi hard-cap aktif (Apple/NVDA/sektor)
                    cap_src = sat.get("cap_source")
                    if cap_src:
                        cap_msg = {
                            "Apple tavani": "🍎 Apple piyasa degeri tavani aktif",
                            "NVDA tavani":  "🎯 NVDA piyasa degeri tavani aktif (Reality Check)",
                            "Sektor Lideri (Reality Check)":
                                "⚡ Sektor lideri piyasa degeri tavani aktif",
                        }.get(cap_src, cap_src)
                        st.caption(f"**Reality Check:** {cap_msg}")

                    # TAM + P/S + Saturation gostergesi
                    if sat.get("sector"):
                        st.caption(f"**Sektor:** {sat['sector']}  |  "
                                     f"**TAM 10y:** "
                                     f"${sat.get('tam_projected_bn_10y', 0):.0f}bn  |  "
                                     f"**P/S carpani:** {sat.get('ps_multiplier', 0):.0f}x")
                        if sat.get("max_realistic_market_cap_bn"):
                            st.caption(f"**Makul max MCap:** "
                                         f"${sat['max_realistic_market_cap_bn']:.0f}bn "
                                         f"= TAM x P/S x %{sat.get('realistic_share_pct', 0):.0f} "
                                         f"x 50% saturasyon limiti")
                        if sat.get("implied_market_cap_at_target_bn") is not None:
                            st.caption(f"**10y Tahmin MCap:** "
                                         f"${sat['implied_market_cap_at_target_bn']:.0f}bn")

                    snap = fc.get("snapshots", {})
                    st.markdown("**Yillik Snapshot:**")
                    for y in ("1y", "3y", "5y", "10y"):
                        if y in snap:
                            s = snap[y]
                            st.caption(f"**{y}** → {fmt_price(s['price'], t)}  "
                                       f"({s['multiple']}x, "
                                       f"{s['change_pct']:+.0f}%)")


def render_fundamentals(results: dict):
    st.markdown("## 💰 Temel Analiz")
    rows = []
    for t, r in results.items():
        f = r["fundamental"]
        rows.append({
            "Hisse": t, "Sektor": f.get("sector", "-"),
            "Piyasa Degeri": f.get("market_cap_human", "-"),
            "Gelir Buyumesi %": round(f.get("revenue_growth_pct", 0), 1),
            "Kar Marji %": round(f.get("profit_margin_pct", 0), 1),
            "Op. Nakit Akisi (M$)": round(f.get("operating_cashflow", 0)/1e6, 1),
            "Beta": round(f.get("beta", 1), 2),
            "Analist Hedef": f"${f.get('target_mean_price', 0):.2f}",
            "Upside %": round(f.get("analyst_upside_pct", 0), 1),
            "Fundamental Score": f["score"],
            "Rating": f["rating"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                 column_config={"Fundamental Score": st.column_config.ProgressColumn(
                     "Fundamental Score", min_value=0, max_value=100)})


def render_radar(results: dict):
    """Radar/Watchlist: 10 yil vizyonlu kuresel tarama."""
    st.markdown("## 📡 Radar - Global Watchlist (10 Yil Vizyonu)")
    st.caption("ABD + Avrupa (ASML) + Cin (HKG: SMIC 0981.HK, Hua Hong 1347.HK) + "
               "AXTI/NVTS/INDI/QUBT. Otomatik 10y CAGR, durability, R&D gucu, "
               "10 yil projeksiyon.")

    watchlist = st.session_state.get("watchlist", [])
    if not watchlist:
        st.info("Sol panelden hisse ekle.")
        return

    rows = []
    for t in watchlist:
        with st.spinner(f"{t} analiz..."):
            res = cached_watchlist(t)
        if not res:
            st.error(f"{t}: veri alinamadi. yfinance Hong Kong/Shanghai datasi"
                     f" bazen kisitli. Alternatif: `akshare` veya `investpy`.")
            continue
        durab = res["durability"]
        raw = durab.get("raw", {})
        curr = cached_currency(t)
        rows.append({
            "Hisse": t,
            "Bolge": "🇨🇳" if t in CHINA_TICKERS else ("🇳🇱" if t == "ASML" else "🇺🇸"),
            "Para": curr,
            "Son Fiyat": res["last_price"],
            "USD Esd.": round(to_usd(res["last_price"], curr), 2),
            "10y CAGR %": res["cagr_10y"].get("cagr_pct", 0),
            "5y CAGR %": res["cagr_5y"].get("cagr_pct", 0),
            "1y CAGR %": res["cagr_1y"].get("cagr_pct", 0),
            "10y Proj.": res["projected_10y"],
            "10y x":     res["projected_multiple_10y"],
            "Durability": durab.get("durability", 0),
            "Gross Margin %": round(raw.get("gross_margin_pct", 0), 1),
            "R&D Intensity %": round(raw.get("rd_intensity_pct", 0), 2),
            "10y Tutma": durab.get("rating", "-"),
        })
    if not rows:
        return
    df = pd.DataFrame(rows).sort_values("Durability", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config={
                     "Durability": st.column_config.ProgressColumn(
                         "Durability", min_value=0, max_value=100, format="%d/100"),
                     "Gross Margin %": st.column_config.ProgressColumn(
                         "Gross Margin %", min_value=-50, max_value=100, format="%.1f%%"),
                 })

    st.markdown("### Hisse Detayi")
    sel = st.selectbox("Detay icin sec", watchlist, key="radar_sel")
    res = cached_watchlist(sel)
    if not res:
        return
    d = res["durability"]
    curr = cached_currency(sel)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Durability Score", f"{d.get('durability', 0)}/100",
                  d.get("rating", "-"))
        st.caption(d.get("verdict", ""))
    with c2:
        st.metric("10y CAGR", f"{res['cagr_10y'].get('cagr_pct', 0):+.1f}%")
        st.metric("5y CAGR", f"{res['cagr_5y'].get('cagr_pct', 0):+.1f}%")
    with c3:
        st.metric("Bugun", fmt_price(res["last_price"], sel),
                  f"USD ~${to_usd(res['last_price'], curr):.2f}" if curr != "USD" else None)
        st.metric("10 yil sonra (proj.)", fmt_price(res["projected_10y"], sel),
                  f"{res['projected_multiple_10y']}x")

    st.markdown("#### Durability Bilesenleri (6 boyut)")
    bd = d.get("breakdown", {})
    # Max degerler (boyut bazli)
    max_map = {"balance_sheet": 18, "revenue_quality": 18, "cash_generation": 18,
               "sustainability": 16, "growth_potential": 16, "tech_moat": 14}
    if bd:
        bd_df = pd.DataFrame([{"Bilesen": k.replace("_", " ").title(),
                                "Puan": v,
                                "Max": max_map.get(k, 20),
                                "Doluluk %": v / max_map.get(k, 20) * 100}
                               for k, v in bd.items()])
        fig = px.bar(bd_df, x="Bilesen", y="Doluluk %", text="Puan",
                      range_y=[0, 100], color="Doluluk %",
                      color_continuous_scale="RdYlGn")
        fig.update_layout(template="plotly_dark", height=300,
                          paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24")
        st.plotly_chart(fig, use_container_width=True, key=f"durab_bd_{sel}")

    st.markdown("#### Ham Finansal + R&D Verisi")
    raw = d.get("raw", {})
    cols = st.columns(3)
    keys = list(raw.keys())
    for i, k in enumerate(keys):
        with cols[i % 3]:
            label = k.replace("_pct", " %").replace("_", " ").title()
            val = raw[k]
            st.write(f"**{label}:** {val:.2f}" if isinstance(val, (int, float)) else f"**{label}:** {val}")

    if curr != "USD":
        st.info(f"ℹ️  {sel} fiyatlari **{curr}** cinsinden. yfinance Hong Kong/Shanghai "
                f"verisini cekiyor; veri gelmezse fallback olarak `akshare` veya "
                f"`investpy` kutuphanesi onerilir.")


def render_milestones(results: dict):
    st.markdown("## 📅 Milestone (Kilometre Tasi) Zaman Cizelgesi")
    st.caption("Statik veritabani + haber akisindan otomatik cikarilan tarihler. "
               "Mavi = bilinen roadmap, sari = haberlerden.")

    all_tickers = list(results.keys()) + st.session_state.get("watchlist", [])
    all_tickers = list(dict.fromkeys(all_tickers))  # uniq

    tabs = st.tabs(all_tickers)
    for tab, t in zip(tabs, all_tickers):
        with tab:
            # Haber datasi: ana hisseler icin sentiment'tan, watchlist icin yeni cek
            news = []
            if t in results:
                news = results[t]["sentiment"].get("news_raw", [])
            else:
                try:
                    from data_fetcher import fetch_yfinance_news
                    news = fetch_yfinance_news(t, limit=10)
                except Exception:
                    news = []
            try:
                timeline = get_timeline(t, news)
            except Exception as e:
                st.error(f"Timeline hatasi: {e}")
                continue
            if timeline.empty:
                st.info(f"{t} icin milestone bulunamadi.")
                continue
            st.plotly_chart(plot_timeline(timeline, t),
                            use_container_width=True, key=f"tl_{t}")
            st.dataframe(timeline[["date", "tag", "event", "source"]],
                         use_container_width=True, hide_index=True)


def render_dca(results: dict):
    st.markdown("## 💵 DCA Calculator (Aylik Sabit Yatirim)")
    st.caption("Her ay sabit miktar yatirsaydim ne olurdu?  Gecmis veri + 10 yil "
               "ileri projeksiyon (volatiliteyle alt/ust bant).")

    tickers_to_run = list(results.keys()) + st.session_state.get("watchlist", [])
    tickers_to_run = list(dict.fromkeys(tickers_to_run))

    c1, c2, c3 = st.columns(3)
    monthly = c1.number_input("Aylik miktar ($)", min_value=10, max_value=10000,
                                value=100, step=50)
    years_back = c2.slider("Gecmis kac yil?", 1, 10, 10)
    years_forward = c3.slider("Ileri kac yil?", 1, 20, 10)

    if st.button("Hesapla", type="primary"):
        st.session_state["dca_run"] = True

    if not st.session_state.get("dca_run"):
        st.info("Yukaridan parametreleri secip 'Hesapla' butonuna bas.")
        return

    # Portfoy ozeti (tum hisseler)
    st.markdown("### 📊 Portfoy Ozeti (Tum Hisseler)")
    with st.spinner("Tum hisseler icin DCA simulasyonu..."):
        portfolio = portfolio_dca(tickers_to_run, monthly, years_back, years_forward)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Yatirilan (Gecmis)", f"${portfolio['historical_invested']:,.0f}")
    m2.metric("Bugunku Bakiye", f"${portfolio['historical_total_value']:,.0f}",
              f"{portfolio['historical_return_pct']:+.1f}%")
    m3.metric(f"{years_forward}y Beklenen",
              f"${portfolio['projected_central_value']:,.0f}",
              f"{(portfolio['projected_central_value']/portfolio['projected_invested']-1)*100:+.1f}%" if portfolio['projected_invested'] else "0%")
    m4.metric(f"{years_forward}y Iyi/Kotu",
              f"${portfolio['projected_up_value']:,.0f}",
              f"alt: ${portfolio['projected_down_value']:,.0f}")

    # Hisse bazli detaylar
    st.markdown("### Hisse Detayli")
    rows = []
    for t in tickers_to_run:
        h = portfolio["historical"].get(t, {})
        p = portfolio["projected"].get(t, {})
        rows.append({
            "Hisse": t,
            "Gecmis Yatirilan": h.get("invested", 0),
            "Bugun Bakiye": h.get("final_value", 0),
            "Gecmis Return %": h.get("return_pct", 0),
            "Gecmis IRR %": h.get("irr_annual_pct", 0),
            "Toplam Hisse": h.get("total_shares", 0),
            "Proj. Beklenen": p.get("final_central", 0),
            "Proj. Iyi": p.get("final_up", 0),
            "Proj. Kotu": p.get("final_down", 0),
            "Carpan (proj.)": p.get("multiple_central", 0),
            "CAGR Kullanilan %": p.get("cagr_used_pct", 0),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Hisse hisse grafik
    st.markdown("### Hisse Grafikleri")
    sub_tabs = st.tabs(tickers_to_run)
    for tab, t in zip(sub_tabs, tickers_to_run):
        with tab:
            h = portfolio["historical"].get(t)
            p = portfolio["projected"].get(t)
            c1, c2 = st.columns(2)
            with c1:
                if h and not h["timeline"].empty:
                    st.plotly_chart(plot_dca_growth(h["timeline"], t),
                                    use_container_width=True, key=f"dca_h_{t}")
                else:
                    st.info("Gecmis veri yok.")
            with c2:
                if p and not p["timeline"].empty:
                    st.plotly_chart(plot_dca_projection(p["timeline"], t),
                                    use_container_width=True, key=f"dca_p_{t}")
                else:
                    st.info("Projeksiyon olusturulamadi.")


def render_vision(results: dict):
    """Visionary Goals - sirketlerin Buyuk Vizyon ilerlemesi."""
    st.markdown("## 🎯 Visionary Goals - 10 Yillik Vizyon Takibi")
    st.caption("milestones.json'daki her sirket icin **anahtar kelime + regex** "
               "tabanli haber tarayici. **Atilim** -> +20 Vision Bonus | "
               "**Gecikme** -> -15. Master Score'a otomatik eklenir.")

    # Tum hisseleri tarama: hem core hem watchlist
    all_tickers = list(results.keys())
    for t in st.session_state.get("watchlist", []):
        if t not in all_tickers and get_vision(t):
            all_tickers.append(t)

    # Tablo: tum hisseler icin vizyon ozeti
    rows = []
    for t in all_tickers:
        r = results.get(t)
        if r and r.get("vision"):
            v = r["vision"]
        else:
            # Watchlist hissesi - haber yok, sadece vizyon db'sinden goster
            v = scan_vision(t, [])
        if not v.get("has_vision"):
            continue
        rows.append({
            "Hisse": t,
            "Hedef": v["vision"].get("current_milestone", "-"),
            "Hedef Tarihi": v["vision"].get("target_date", "-"),
            "Atilim Sinyali": v.get("n_achievements", 0),
            "Gecikme Sinyali": v.get("n_delays", 0),
            "Vision Bonus": v.get("vision_bonus", 0),
            "Rating": v.get("rating", "-"),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                     hide_index=True,
                     column_config={
                         "Vision Bonus": st.column_config.NumberColumn(
                             "Vision Bonus",
                             help="-15 (kriz) ile +20 (atilim) arasi. "
                                  "Master Score'a eklenir.")})

    # Hisse hisse detaylar
    st.markdown("### Sirket Vizyon Kartlari")
    sel = st.selectbox("Hisse sec", all_tickers, key="vision_sel")
    r = results.get(sel)
    if r and r.get("vision"):
        v = r["vision"]
        news = r["sentiment"].get("news_raw", [])
    else:
        v = scan_vision(sel, [])
        news = []
    if not v.get("has_vision"):
        st.warning(f"{sel} icin milestones.json'da vizyon kaydi yok. "
                   "milestones.json'a ekleyebilirsin.")
        return

    vd = v["vision"]
    # Buyuk Vizyon karti
    rating_color = {
        "ATILIM": "#00c853", "ILERLEME": "#64dd17",
        "NOTR": "#ffc107", "GECIKME": "#ff6e40", "KRIZ": "#d50000",
    }.get(v["rating"], "#888")

    st.markdown(
        f"""
        <div style='background:#1a1d24;border-left:6px solid {rating_color};
                    padding:14px;border-radius:8px;margin-bottom:16px'>
          <h3 style='color:white;margin:0'>{vd.get('name', sel)}</h3>
          <p style='color:#bdbdbd;margin:6px 0 12px 0;font-size:14px'>
            <b>BUYUK VIZYON:</b> {vd.get('big_vision', '-')}
          </p>
          <p style='color:white;margin:0'>
            <b>Su anki Donum Noktasi:</b> {vd.get('current_milestone', '-')}<br>
            <b>Hedef Tarih:</b> {vd.get('target_date', '-')}  |
            <b>North-Star Metrik:</b> {vd.get('north_star_metric', '-')}
            ({vd.get('current_value', 0)} → {vd.get('target_value', 0)})
          </p>
        </div>
        """, unsafe_allow_html=True)

    # Vision Bonus ve rating
    c1, c2, c3 = st.columns(3)
    c1.metric("Vision Bonus", f"{v['vision_bonus']:+d}",
              v["rating"])
    c2.metric("Atilim Sinyali", v.get("n_achievements", 0),
              "haberdden tespit")
    c3.metric("Gecikme Sinyali", v.get("n_delays", 0),
              "haberdden tespit")
    st.info(v.get("message", ""))

    # North-star progress bar (anahtar metrige ilerleme)
    cur = vd.get("current_value", 0) or 0
    tgt = vd.get("target_value", 1) or 1
    if tgt > 0:
        progress = min(1.0, cur / tgt) if tgt > 0 else 0
        st.markdown(f"**Hedefe Ilerleme:** {vd.get('north_star_metric', '-')}: "
                    f"{cur} / {tgt}  ({progress*100:.0f}%)")
        st.progress(progress)

    # Achievement / Delay haberleri
    col_a, col_d = st.columns(2)
    with col_a:
        st.markdown("#### 🎯 Atilim Haberleri")
        if v["achievements"]:
            for a in v["achievements"][:5]:
                st.success(f"✅ **{a['title']}**\n\n"
                           f"_Eslesme:_ `{a['pattern_match'][:80]}`")
        else:
            st.caption("Henuz vizyon atilimi yok.")
    with col_d:
        st.markdown("#### ⚠️ Gecikme/Risk Haberleri")
        if v["delays"]:
            for d in v["delays"][:5]:
                st.error(f"⚠️ **{d['title']}**\n\n"
                         f"_Eslesme:_ `{d['pattern_match'][:80]}`")
        else:
            st.caption("Stratejik gecikme sinyali yok.")

    # Anahtar kelime gecisleri (rotasyonsuz)
    if v.get("keyword_hits"):
        st.markdown("#### 🔍 Anahtar Kelime Tespitleri")
        for h in v["keyword_hits"][:8]:
            st.caption(f"• `{h['keyword']}` — {h['title']}")

    # Stratejik Beklenti overlay (IONQ/RGTI/ATOM/LAES)
    if r and r.get("strategic_overlay"):
        so = r["strategic_overlay"]
        if so.get("overlay_bonus", 0) != 0 or so.get("labels"):
            st.markdown("#### 🧬 Stratejik Beklenti Katmani")
            st.metric("Overlay Bonus (Master)",
                       f"{so.get('overlay_bonus', 0):+d} puan",
                       so.get("overlay_type", ""))
            for lbl in so.get("labels", []):
                st.caption(lbl)
            for w in so.get("warnings", []):
                st.warning(w)
            if so.get("evidence"):
                with st.expander("Kanıt haberleri"):
                    for ev in so["evidence"][:5]:
                        link = ev.get("link", "")
                        title = ev.get("title", "")
                        tag = ev.get("tag", "")
                        if link:
                            st.markdown(f"`{tag}` [{title}]({link})")
                        else:
                            st.markdown(f"`{tag}` {title}")

    # Moonshot J-Curve dedektoru (NVTS, INDI, RGTI + secondary)
    if r and r.get("moonshot") and r["moonshot"].get("is_moonshot_candidate"):
        m = r["moonshot"]
        ribbon = "🚀 MOONSHOT CANDIDATE" if m.get("is_primary_moonshot") \
                  else "🚁 Secondary Moonshot"
        st.markdown(f"#### {ribbon} - J-Curve Detector")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("J-Curve Score",
                   f"{m.get('j_curve_score', 0):.0f}/100",
                   f"Master {m.get('master_bonus', 0):+d}")
        c2.metric("Revenue YoY",
                   f"%{m.get('revenue_yoy_pct'):+.0f}"
                       if m.get("revenue_yoy_pct") is not None else "-")
        c3.metric("R&D YoY",
                   f"%{m.get('rd_yoy_pct'):+.0f}"
                       if m.get("rd_yoy_pct") is not None else "-")
        c4.metric("2y Revenue Mult.",
                   f"{m.get('revenue_multiplier')}x"
                       if m.get("revenue_multiplier") is not None else "-")
        if m.get("backlog_growth_pct") is not None:
            st.caption(f"📦 Backlog (Inventory+Receivables) YoY: "
                        f"%{m['backlog_growth_pct']:+.0f}")
        st.caption(m.get("rationale", ""))
        for lbl in m.get("labels", [])[:6]:
            st.caption(lbl)
        if r.get("explosive_factor") and r["explosive_factor"] != "-":
            st.info(f"**Explosive Factor:** {r['explosive_factor']}")

    # Competitor Benchmark (Relative Strength) - AXTI vs IQE/Sumitomo vb.
    if r and r.get("competitor_benchmark"):
        cb = r["competitor_benchmark"]
        if cb.get("competitors"):
            st.markdown("#### 🥊 Rakip Kiyaslamasi (Relative Strength)")
            c1, c2, c3 = st.columns(3)
            c1.metric(f"{sel} 120g Getiri",
                        f"%{cb.get('ticker_return_pct', 0):+.1f}")
            c2.metric("Rakip Ortalama",
                        f"%{cb.get('competitor_avg_return_pct', 0):+.1f}")
            c3.metric("Relative Strength",
                        f"{cb.get('relative_strength_pp', 0):+.1f}pp",
                        f"Bonus: {cb.get('bonus', 0):+d}")
            st.caption(cb.get("label", "") + " — " + cb.get("narrative", ""))
            if cb.get("per_competitor"):
                pc_df = pd.DataFrame([
                    {"Rakip": s, "120g Getiri %": v}
                    for s, v in cb["per_competitor"].items()
                ])
                pc_df = pc_df.sort_values("120g Getiri %", ascending=False)
                st.dataframe(pc_df, use_container_width=True, hide_index=True,
                              column_config={"120g Getiri %":
                                  st.column_config.NumberColumn(
                                      "120g Getiri %", format="%+.1f%%")})

    # Cash Runway (speculative)
    if r and r.get("cash_runway"):
        cr = r["cash_runway"]
        if cr.get("runway_months") is not None or cr.get("is_unsustainable"):
            st.markdown("#### 💵 Finansal Surdurulebilirlik (Cash Runway)")
            rm = cr.get("runway_months")
            rm_disp = f"{rm:.0f} ay" if rm and rm < 999 else "Karli / belirsiz"
            st.metric("Cash Runway", rm_disp, cr.get("label", ""))
            if cr.get("is_unsustainable"):
                st.error(
                    f"⚠️ **Finansal Surdurulebilirlik Riski**: Nakit "
                    f"${cr.get('cash_usd_m', 0):.0f}M, ceyreklik burn "
                    f"${cr.get('quarterly_burn_usd_m', 0):.0f}M. "
                    f"Master Score'a {cr.get('master_penalty', 0)} ceza uygulandi. "
                    f"Spekulatif hisse - pozisyon boyutunu kucult.")
            elif cr.get("is_warning"):
                st.warning(f"Cash runway izleme modunda: {rm_disp}")

    if is_speculative(sel):
        st.caption("🏷️ **Speculative Risk** etiketi aktif - yuksek volatilite "
                    "ve teknoloji riski.")

    # ASML/SMIC ozel kritik agirlik
    if sel in ("ASML", "0981.HK") and r and r.get("critical_weight"):
        cw = r["critical_weight"]
        if cw.get("weight"):
            st.markdown("#### 🌐 EUV / Cin-ABD Tekno Savasi Etki")
            st.metric("Master Score Etkisi", f"{cw['weight']:+d} puan")
            for c in cw.get("context", [])[:5]:
                st.caption(f"• `{c['term']}` ({c['pts']:+d}) — {c['title']}")


def render_sector(results: dict, histories: dict):
    """Sektorel Zeka - Capex Watch + Pair Trading + Volatility + Moat."""
    st.markdown("## 🏭 Sektorel Zeka - Yari Iletken Takip Istasyonu")
    st.caption("Capex Watch (TSMC/Samsung/Intel) | Correlation Matrix + Pair Trading "
               "| Volatility Smile (Korku Endeksi) | Moat Analysis (R&D < %15 uyarisi)")

    # ============ 1) Capex Watch ====================================
    st.markdown("### 1️⃣ Capex Watch - Foundry Devleri")
    with st.spinner("Capex haberleri taraniyor..."):
        capex_scan = cached_capex_scan()
    if capex_scan:
        rows = []
        for g, data in capex_scan.items():
            rows.append({
                "Sirket": g, "Adi": data["name"],
                "Sinyal": data["signal"],
                "Pozitif Haber": data["n_pos"],
                "Negatif Haber": data["n_neg"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     column_config={"Sinyal": st.column_config.NumberColumn(
                         "Sinyal", help="-10 (cut) ile +10 (yatirim artisi) arasi")})

        # Hisse bazli capex etkisi
        st.markdown("**Bizim hisselere etki:**")
        impact_rows = []
        for t, r in results.items():
            cw = r.get("capex_weight", {})
            impact_rows.append({
                "Hisse": t,
                "Capex Etkisi": cw.get("capex_weight", 0),
                "Etiket": cw.get("label", "-"),
                "Kaynak Sayisi": len(cw.get("contributors", [])),
            })
        st.dataframe(pd.DataFrame(impact_rows), use_container_width=True,
                     hide_index=True)
    else:
        st.info("Capex verisi cekilemedi.")

    st.divider()

    # ============ 2) Correlation + Pair Trading ====================
    st.markdown("### 2️⃣ Correlation Matrix + Pair Trading")
    with st.spinner("Korelasyon matrisi hesaplaniyor..."):
        corr = build_correlation(histories, window_days=60)
    if not corr.empty:
        fig_corr = px.imshow(corr, text_auto=".2f", aspect="auto",
                              color_continuous_scale="RdBu", range_color=[-1, 1],
                              title="60-gun Gunluk Getiri Korelasyonu")
        fig_corr.update_layout(template="plotly_dark", height=420,
                                paper_bgcolor="#0e1117")
        st.plotly_chart(fig_corr, use_container_width=True, key="corr_matrix")

    # Pair Trading firsatlari
    st.markdown("**Pair Trading Firsatlari** (yuksek korelasyon + asimmetrik ayrisma):")
    pairs = find_pair_opportunities(histories, min_corr=0.40,
                                     zscore_threshold=1.5, lookback_days=90)
    if pairs:
        pdf = pd.DataFrame(pairs)[["pair", "correlation", "zscore",
                                     "long", "short", "ratio",
                                     "ratio_mean_30d", "signal_strength"]]
        st.dataframe(pdf, use_container_width=True, hide_index=True,
                     column_config={
                         "signal_strength": st.column_config.ProgressColumn(
                             "Sinyal %", min_value=0, max_value=100, format="%.0f")})
        st.info(f"En guclu firsat: **{pairs[0]['pair']}** "
                f"(z={pairs[0]['zscore']:+.2f}). "
                f"Onerim: **LONG {pairs[0]['long']}** + **SHORT {pairs[0]['short']}**.")
    else:
        st.caption("Su an pair trading firsati yok (z-score esiginin altinda).")

    # Goreceli performans
    st.markdown("**Goreceli Performans (son 90 gun):**")
    rel = relative_performance(histories, lookback_days=90)
    if not rel.empty:
        fig_rel = px.bar(rel, x="ticker", y="return_pct",
                          color="return_pct", color_continuous_scale="RdYlGn",
                          text="return_pct")
        fig_rel.update_layout(template="plotly_dark", height=280,
                               paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24")
        st.plotly_chart(fig_rel, use_container_width=True, key="rel_perf")

    st.divider()

    # ============ 3) Volatility Smile / Fear ======================
    st.markdown("### 3️⃣ Volatility Smile - Korku Endeksi")
    st.caption("yfinance opsiyon zincirinden ATM IV + OTM put/call skew. "
               "Yuksek IV + put skew = piyasa korkusu.")

    if st.button("📡 Tum hisselerin IV'sini cek", key="iv_scan_btn"):
        st.session_state["iv_scan_done"] = True
    iv_rows = []
    if st.session_state.get("iv_scan_done"):
        with st.spinner("Opsiyon zincirleri yukleniyor (yavas)..."):
            for t in results:
                iv = cached_iv(t)
                if iv.get("success"):
                    iv_rows.append({
                        "Hisse": t, "Spot ($)": iv["spot"],
                        "ATM IV %": iv["atm_iv_pct"],
                        "Put IV %": iv["put_iv_pct"],
                        "Call IV %": iv["call_iv_pct"],
                        "Skew (pp)": iv["skew_pp"],
                        "Fear Score": iv["fear_score"],
                        "Etiket": iv["fear_label"],
                        "Vade": iv["nearest_expiry"],
                    })
                else:
                    iv_rows.append({
                        "Hisse": t, "Etiket": "VERI YOK", "Fear Score": 0,
                        "Spot ($)": 0, "ATM IV %": 0, "Put IV %": 0,
                        "Call IV %": 0, "Skew (pp)": 0, "Vade": "-",
                    })
    if iv_rows:
        st.dataframe(pd.DataFrame(iv_rows), use_container_width=True, hide_index=True,
                     column_config={"Fear Score": st.column_config.ProgressColumn(
                         "Fear", min_value=0, max_value=100, format="%.0f")})

    st.divider()

    # ============ 4) Moat Analysis ===================================
    st.markdown("### 4️⃣ Moat Analysis - R&D Yogunlugu (%15 esigi)")
    st.caption("Sirketlerin Ar-Ge / Toplam Gelir orani. <%15 = Inovasyon Riski.")
    moat_rows = []
    for t in results:
        m = cached_moat(t)
        moat_rows.append({
            "Hisse": t,
            "R&D %": m["rd_pct"],
            "R&D ($M)": m["rd_dollars_m"],
            "Gelir ($M)": m["revenue_m"],
            "Gross Margin %": m["gross_margin_pct"],
            "Operating Margin %": m["operating_margin_pct"],
            "Moat Rating": m["moat_rating"],
            "Inovasyon Riski": "⚠️ EVET" if m["innovation_risk"] else "✅ HAYIR",
            "Pricing Power": m["pricing_power"],
        })
    moat_df = pd.DataFrame(moat_rows).sort_values("R&D %", ascending=False)
    st.dataframe(moat_df, use_container_width=True, hide_index=True,
                 column_config={
                     "R&D %": st.column_config.ProgressColumn(
                         "R&D %", min_value=0, max_value=50, format="%.1f%%"),
                     "Gross Margin %": st.column_config.ProgressColumn(
                         "Gross Margin %", min_value=-30, max_value=100,
                         format="%.1f%%"),
                 })

    # Inovasyon riski uyarilari
    risky = [r for r in moat_rows if "EVET" in r["Inovasyon Riski"]]
    if risky:
        st.error("⚠️ **Inovasyon Riski** taşıyan hisseler (R&D < %15): " +
                 ", ".join([r["Hisse"] for r in risky]))

    st.divider()

    # ============ 5) Sektorel Zincirler ============================
    st.markdown("### 5️⃣ Sektorel Zincirler (NVDA → ASML, EV → WOLF)")
    chains = cached_sector_chains()
    if chains:
        rows = []
        for k, data in chains.items():
            if not data:
                continue
            rows.append({
                "Zincir": k,
                "Anlatim": data.get("narrative", "-"),
                "Liderler": ", ".join(data.get("leader_rets", {}).keys()),
                "Lider Ort. %": data.get("leader_avg_pct", 0),
                "Sinyal": data.get("signal", 0),
                "Etkilenenler": ", ".join(data.get("followers", [])),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Detayli zincir
        st.markdown("**Hisse Bazli Sektorel Etki:**")
        impact_rows = []
        for t, r in results.items():
            sw = r.get("sector_weight", {})
            impact_rows.append({
                "Hisse": t,
                "Sektorel Etki": sw.get("sector_weight", 0),
                "Etiket": sw.get("label", "-"),
                "Zincir Sayisi": len(sw.get("chains", [])),
            })
        st.dataframe(pd.DataFrame(impact_rows), use_container_width=True,
                     hide_index=True)


def render_hardware_intel(results: dict):
    """Hardware Intelligence Agent - 24h cache, patent/geo/yield/cycle."""
    st.markdown("## 🛰 Hardware Intelligence Agent (HIA)")
    st.caption("24-saatlik web arastirma ajani. Patent + Geopolitics + "
                "Yield/Fab + Semi Cycle. Sonuclar `data/research_cache.json` "
                "+ `milestones.json` (Confirmed by Web Research etiketi) "
                "olarak kaydedilir.")

    intel = get_intel()
    age = cache_age_hours()
    stale = is_stale()

    # ----- Header / Cache durumu ---------------------------------
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if age is None:
            st.metric("Son Tarama", "Hic Yok", "Lutfen tara")
        else:
            st.metric("Son Tarama", f"{age:.1f} saat once",
                      "FRESH" if not stale else "STALE",
                      delta_color="normal" if not stale else "inverse")
    with c2:
        cycle = intel.get("semi_cycle", {})
        st.metric("Semi Cycle Fazi",
                   cycle.get("phase", "❓")[:30],
                   f"Skor {cycle.get('cycle_score', 0)}/100")
    with c3:
        n_patents = sum(p.get("strategic_hits", 0) for p in
                          intel.get("patents", {}).values()
                          if isinstance(p, dict))
        st.metric("Toplam Stratejik Patent", n_patents)
    with c4:
        critical_geo = [t for t, g in intel.get("geopolitics", {}).items()
                          if isinstance(g, dict) and g.get("critical_alert")]
        st.metric("🚨 Kritik Geo Alarm", len(critical_geo),
                   ", ".join(critical_geo) if critical_geo else "Yok",
                   delta_color="inverse" if critical_geo else "normal")

    # ----- Kontroller ---------------------------------------------
    colA, colB = st.columns([1, 3])
    with colA:
        force = st.button("🔄 SIMDI YENIDEN TARA (force)",
                            type="primary",
                            disabled=False)
    with colB:
        st.caption("Otomatik: cache 24+ saatlik ise sayfa yuklendiginde "
                    "arka planda calisir. Tum ABD + Avrupa + Cin hisselerini "
                    "tarar (~2-3 dakika).")

    if force:
        progress = st.progress(0.0, text="Baslatiliyor...")
        def _cb(msg, frac):
            try:
                progress.progress(frac, text=msg)
            except Exception:
                pass
        try:
            run_scan(force=True, progress_cb=_cb)
            st.success("Tarama tamamlandi! Sayfayi yenile.")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Tarama hatasi: {e}")
        progress.empty()
        intel = get_intel()

    if not intel or not intel.get("last_run"):
        st.warning("HIA henuz hic calistirilmadi. Yukarıdaki butona basin.")
        return

    st.divider()

    # ----- Supply Chain Risk Flasor -------------------------------
    st.markdown("### 🚨 Supply Chain Risk Radar")
    geo = intel.get("geopolitics", {})
    geo_rows = []
    critical_list = []
    for t in sorted(geo.keys()):
        g = geo[t]
        if not isinstance(g, dict) or g.get("error"):
            continue
        risk = g.get("risk_score", 0)
        geo_rows.append({
            "Hisse": t,
            "Risk Skoru": risk,
            "Risk Seviyesi": g.get("risk_level", "-"),
            "Negatif Haber": g.get("n_negative", 0),
            "Pozitif Haber": g.get("n_positive", 0),
            "Master Etki": g.get("export_weight", 0),
        })
        if g.get("critical_alert"):
            critical_list.append((t, g))

    if critical_list:
        for t, g in critical_list:
            st.error(f"🚨🚨🚨 **{t} - {g['risk_level']}** "
                      f"(Risk Skoru: {g['risk_score']})")
            for item in g.get("negative_items", [])[:3]:
                st.markdown(f"- **{item.get('title', '')[:160]}** "
                              f"_{item.get('source', '')}_")

    if geo_rows:
        st.dataframe(pd.DataFrame(geo_rows), use_container_width=True,
                      hide_index=True,
                      column_config={"Risk Skoru":
                          st.column_config.NumberColumn(
                              "Risk Skoru",
                              help=">0 olumlu, <0 negatif (-10..+10)")})

    st.divider()

    # ----- Patent Intelligence ------------------------------------
    st.markdown("### 🏆 Patent & IP Watch")
    patents = intel.get("patents", {})
    pat_rows = []
    for t in sorted(patents.keys()):
        p = patents[t]
        if not isinstance(p, dict) or p.get("error"):
            continue
        pat_rows.append({
            "Hisse": t,
            "Stratejik Patent": p.get("strategic_hits", 0),
            "Toplam Sonuc": p.get("total_hits", 0),
            "Bonus (Master)": p.get("patent_bonus", 0),
            "Etiket": p.get("label", "-"),
        })
    if pat_rows:
        pat_df = pd.DataFrame(pat_rows).sort_values("Stratejik Patent",
                                                       ascending=False)
        st.dataframe(pat_df, use_container_width=True, hide_index=True,
                      column_config={"Bonus (Master)":
                          st.column_config.ProgressColumn(
                              "Bonus (Master)", min_value=0, max_value=5,
                              format="%d")})

        # En aktif patent sirketi detayi
        top_t = pat_df.iloc[0]["Hisse"]
        if pat_df.iloc[0]["Stratejik Patent"] > 0:
            st.markdown(f"**🥇 {top_t} - En Guncel 3 Patent/IP Hareketi:**")
            for item in patents[top_t].get("recent_items", [])[:3]:
                title = item.get("title", "Baslik yok")
                link = item.get("link", "")
                src = item.get("source", "")
                if link:
                    st.markdown(f"- [{title[:200]}]({link}) _{src}_")
                else:
                    st.markdown(f"- {title[:200]} _{src}_")

    st.divider()

    # ----- Yield & Fab Intelligence -------------------------------
    st.markdown("### 🏭 Yield & Fab Intelligence (Production Health)")
    yi = intel.get("yield_intel", {})
    y_rows = []
    for t in sorted(yi.keys()):
        y = yi[t]
        if not isinstance(y, dict) or y.get("error"):
            continue
        y_rows.append({
            "Hisse": t,
            "Yield %": y.get("avg_yield_pct") or "-",
            "Veri Noktasi": len(y.get("yield_data_points", [])),
            "Production Health": y.get("production_health", "-"),
            "Production Score": y.get("production_score", 0),
        })
    if y_rows:
        st.dataframe(pd.DataFrame(y_rows), use_container_width=True,
                      hide_index=True,
                      column_config={"Production Score":
                          st.column_config.ProgressColumn(
                              "Production Score", min_value=0, max_value=100,
                              format="%d")})
        # Yield sayisal kanitlar
        sayisal = [t for t in yi if isinstance(yi[t], dict)
                     and yi[t].get("avg_yield_pct")]
        if sayisal:
            st.markdown("**📊 Sayisal Yield Kanitlari:**")
            for t in sayisal[:3]:
                st.markdown(f"**{t}** - {yi[t]['avg_yield_pct']:.1f}% yield")
                for dp in yi[t].get("yield_data_points", [])[:2]:
                    link = dp.get("link", "")
                    title = dp.get("title", "")[:160]
                    if link:
                        st.caption(f"  - [{title}]({link}) "
                                     f"(rapor edilen: %{dp['yield_pct']})")

    st.divider()

    # ----- Semi Cycle Phase Card -----------------------------------
    st.markdown("### 🔄 Semiconductor Cycle Index")
    cycle = intel.get("semi_cycle", {})
    if cycle:
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.metric("Cycle Phase", cycle.get("phase", "?")[:25],
                       cycle.get("cycle_score", 0))
        with c2:
            st.metric("Master Modifier",
                       f"{cycle.get('modifier', 0):+d}",
                       help="Tum hisselerin Master Score'una eklenir")
        with c3:
            st.info(f"**Analiz:** {cycle.get('narrative', '-')}")

        sig = cycle.get("signals", {})
        if sig:
            sig_df = pd.DataFrame([
                {"Sinyal": "SOXX RSI(60)",         "Deger": sig.get("soxx_rsi60")},
                {"Sinyal": "SMH RSI(60)",          "Deger": sig.get("smh_rsi60")},
                {"Sinyal": "Equipment 12m Return", "Deger": sig.get("equipment_12m_pct")},
                {"Sinyal": "Logic 12m Return",     "Deger": sig.get("logic_12m_pct")},
                {"Sinyal": "Memory 12m Return",    "Deger": sig.get("memory_12m_pct")},
                {"Sinyal": "Above-200 SMA breadth %", "Deger": sig.get("above_200_breadth_pct")},
            ])
            st.dataframe(sig_df, use_container_width=True, hide_index=True)

    st.divider()

    # ----- ML Diagnostic (Lopez de Prado + Andrew Ng) -------------
    with st.expander("🧪 ML Akademik Diagnostik (Lopez de Prado MDA + Andrew Ng Error Decomposition)",
                       expanded=False):
        st.caption("Detayli feature importance ve bias/variance hata analizi.")
        try:
            from feature_importance import diagnose_model
            diag_rows = []
            for t, r in results.items():
                ml = r.get("ml", {})
                if not ml:
                    continue
                diag = diagnose_model(ml)
                diag_rows.append({
                    "Hisse": t,
                    "Train Err": diag["train_err"],
                    "Val Err":   diag["val_err"],
                    "Avoidable Bias": diag["avoidable_bias"],
                    "Variance":   diag["variance"],
                    "Tani":       " + ".join(diag["diagnoses"]),
                })
            if diag_rows:
                st.dataframe(pd.DataFrame(diag_rows), use_container_width=True,
                              hide_index=True)
                st.caption("**Yorum:** *YUKSEK BIAS* (underfit) -> model basit, "
                            "veri ekle. *YUKSEK VARIANCE* (overfit) -> "
                            "regularization gerekli.")
        except Exception as e:
            st.warning(f"ML diagnostik hatasi: {e}")


def render_research_agent(results: dict):
    """V7 Deep Research Agent - haber yogunlugu + Lopez de Prado dinamik coef."""
    st.markdown("## 🔬 Deep Research Agent (v7)")
    st.caption("4-saatlik agresif tarama. 'Haber Yogunlugu' (intensity) + net "
                "skor uretir, Lopez de Prado MDA tarzi Master Score'a dinamik "
                "carpan (0.5-1.5) olarak girer. Sonuclar `visionary_goals.json` "
                "icine **'Confirmed by Web Research'** etiketiyle yazilir.")

    cache = get_research_cache()
    age = research_age_hours()
    stale = research_stale()

    # --- Durum + Tarama Butonu ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if age is None:
            st.metric("Son Tarama", "Hic Yok")
        else:
            st.metric("Son Tarama", f"{age:.1f} saat",
                       "FRESH" if not stale else "STALE",
                       delta_color="normal" if not stale else "inverse")
    with c2:
        summ = cache.get("summary", {})
        st.metric("Sektor Avg Intensity",
                   f"{summ.get('avg_intensity', 0):.0f}/100")
    with c3:
        st.metric("Sektor Avg Net Score",
                   f"{summ.get('avg_net_score', 0):+.2f}",
                   "Bullish" if summ.get("avg_net_score", 0) > 0
                   else "Bearish" if summ.get("avg_net_score", 0) < 0
                   else "Notr")
    with c4:
        max_t = summ.get("max_intensity_ticker", "-")
        st.metric("En Yogun Hisse", str(max_t))

    if st.button("🔬 SIMDI DERIN ARASTIR (force)", type="primary",
                   key="research_force"):
        progress = st.progress(0.0, text="Baslatiliyor...")
        def _cb(msg, frac):
            try: progress.progress(frac, text=msg)
            except Exception: pass
        try:
            run_daily_research(force=True, progress_cb=_cb)
            st.success("Arastirma tamamlandi! Sayfayi yenile.")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Arastirma hatasi: {e}")
        progress.empty()
        cache = get_research_cache()

    if not cache or not cache.get("by_ticker"):
        st.warning("Deep Research Agent henuz calistirilmadi. Yukaridaki "
                    "butona basin.")
        return

    st.divider()

    # --- Intensity tablosu ---
    st.markdown("### 📊 Haber Yogunlugu + Dinamik Master Coef")
    st.caption("Lopez de Prado MDA: yuksek intensity + net pozitif sinyal -> "
                "Master Score taban skoru 1.5x'a kadar carpilir.")
    rows = []
    for t in sorted(cache.get("by_ticker", {}).keys()):
        d = cache["by_ticker"][t]
        if not isinstance(d, dict):
            continue
        rows.append({
            "Hisse": t,
            "Intensity": d.get("intensity", 0),
            "Net Score": d.get("net_score", 0),
            "Bull": d.get("bullish", 0),
            "Bear": d.get("bearish", 0),
            "Notr": d.get("neutral", 0),
            "Dinamik Coef": d.get("dynamic_coef", 1.0),
            "Master Etki": f"{(d.get('dynamic_coef',1)-1)*100:+.0f}%",
        })
    if rows:
        df_r = pd.DataFrame(rows).sort_values("Intensity", ascending=False)
        st.dataframe(df_r, use_container_width=True, hide_index=True,
                      column_config={
                          "Intensity": st.column_config.ProgressColumn(
                              "Intensity", min_value=0, max_value=100,
                              format="%d"),
                          "Net Score": st.column_config.NumberColumn(
                              "Net Score", format="%.2f",
                              help="-1 bearish, 0 notr, +1 bullish"),
                          "Dinamik Coef": st.column_config.NumberColumn(
                              "Dinamik Coef", format="%.2f",
                              help="0.5..1.5 -> Master Score'a carpan"),
                      })

    st.divider()

    # --- Headlines ---
    st.markdown("### 📰 Stratejik Manşetler")
    sel = st.selectbox("Hisse Sec:", sorted(cache.get("by_ticker", {}).keys()),
                         key="research_select")
    if sel:
        d = cache["by_ticker"][sel]
        st.markdown(f"**Sorgular:** {d.get('queries_run', 0)}  |  "
                      f"**Toplam Sonuc:** {d.get('total_items', 0)}  |  "
                      f"**Son 30 Gun:** {d.get('recent_items', 0)}")
        if d.get("note"):
            st.info(d["note"])
        for h in d.get("headlines", []):
            cls = h.get("classification", "neutral")
            color = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(cls, "⚪")
            title = h.get("title", "Baslik yok")[:200]
            link = h.get("link", "")
            query = h.get("query", "")
            if link:
                st.markdown(f"{color} **[{title}]({link})**  _{query}_")
            else:
                st.markdown(f"{color} **{title}**  _{query}_")
            if h.get("summary"):
                st.caption(h["summary"][:200])

    st.divider()

    # --- Makro Bonus (Expansion +10) gostergesi ---
    st.markdown("### 📈 Makro Bonus (Semiconductor Cycle)")
    intel = get_intel()
    cycle = intel.get("semi_cycle", {})
    if cycle:
        macro_b = cycle.get("macro_bonus", 0)
        phase = cycle.get("phase", "?")
        if macro_b > 0:
            st.success(f"**{phase}** -> Tum teknoloji hisselerine "
                        f"**+{macro_b}** Makro Bonus uygulaniyor!")
        elif macro_b < 0:
            st.warning(f"**{phase}** -> Tum teknoloji hisselerine "
                        f"**{macro_b}** Makro Cezasi uygulaniyor.")
        else:
            st.info(f"**{phase}** -> Notr makro etki.")
        st.caption(cycle.get("narrative", ""))


def render_logs():
    st.markdown("## 📋 Bildirim Loglari")
    st.caption("Master Score >= 85 -> KRITIK ALIM (toast + log) / >= 70 -> log")
    lines = get_log_tail(50)
    if not lines:
        st.info("Henuz log yok. Master Score 70+ olunca buraya yazilir.")
        return
    for line in reversed(lines):
        if "KRITIK" in line:
            st.error(line.strip())
        elif "GUCLU" in line:
            st.success(line.strip())
        else:
            st.code(line.strip(), language="text")


# ===========================================================================
# Sidebar - Watchlist Manager
# ===========================================================================

def sidebar():
    with st.sidebar:
        st.title("⚙️ Kontrol")
        st.markdown(f"**Cekirdek hisseler:** {', '.join(TICKERS)}")
        st.markdown(f"**Cache:** {REFRESH_MINUTES} dk")

        if st.button("🔄 Simdi Yenile (cache uc)", use_container_width=True,
                       type="primary"):
            st.cache_data.clear()
            _HIST_CACHE.clear()
            # Diger lru_cache'lar
            try:
                from moonshot_detector import detect_moonshot
                detect_moonshot.cache_clear()
            except Exception:
                pass
            try:
                from moat_analysis import get_moat
                get_moat.cache_clear()
            except Exception:
                pass
            st.success("Cache temizlendi - kalibrasyonlar uygulaniyor.")
            st.rerun()

        st.session_state["auto_refresh"] = st.checkbox(
            "Otomatik yenile (15 dk)", value=True, key="auto_refresh_cb")

        # =================================================================
        # TELEGRAM PUSH SETUP - Telefona bildirim
        # =================================================================
        st.divider()
        with st.expander("📲 Telegram Bildirimleri (telefon)", expanded=False):
            try:
                import telegram_notifier as tg
                cfg = tg.load_config()
                if cfg.get("enabled") and cfg.get("bot_token") and cfg.get("chat_id"):
                    st.success(f"✅ Telegram AKTIF (chat: `{cfg['chat_id']}`)")
                else:
                    st.warning("Telegram henuz kurulmadi")
                st.caption(
                    "Kritik haberler (NVTS Tier-1, LAES NIST PQC, ATOM JDA, "
                    "AXTI Ga/Ge ihracat, Master Score >= 85) **telefonuna** "
                    "Telegram uzerinden anlik push olarak gelsin.")
                st.markdown("**1. Bot olustur (30 saniye):**")
                st.caption("Telefonda Telegram'da `@BotFather` ara → `/newbot` → "
                            "isim ver → token al")
                bot_token = st.text_input(
                    "Bot Token", value=cfg.get("bot_token", ""),
                    type="password",
                    placeholder="1234567890:AAEh...",
                    key="tg_bot_token")
                st.markdown("**2. Botunla konus (5 sn):**")
                st.caption("Telegram'da yeni botunu ara → `/start` gonder")
                chat_id = st.text_input(
                    "Chat ID", value=cfg.get("chat_id", ""),
                    placeholder="123456789", key="tg_chat_id")
                colA, colB = st.columns(2)
                with colA:
                    if st.button("🔍 Chat ID Otomatik Bul",
                                   use_container_width=True,
                                   disabled=not bot_token,
                                   key="tg_get_chat"):
                        cid, info = tg.get_chat_id_from_updates(bot_token)
                        if cid:
                            st.session_state["tg_chat_id"] = cid
                            st.success(f"✅ Chat ID: `{cid}` (kullanici: {info})")
                            st.info("Sag ust 'Save' butonuna basip kaydedebilirsin")
                        else:
                            st.error(f"❌ {info}")
                with colB:
                    if st.button("🧪 Test Mesaji Gonder",
                                   use_container_width=True,
                                   disabled=not (bot_token and chat_id),
                                   key="tg_test"):
                        ok, msg = tg.test_connection(bot_token, chat_id)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                enabled = st.checkbox("Bildirimleri AKTIVE et",
                                       value=cfg.get("enabled", False),
                                       key="tg_enabled")
                min_sev = st.selectbox(
                    "Minimum onem seviyesi",
                    options=["KRITIK", "UYARI", "GUCLU", "BILGI"],
                    index=["KRITIK", "UYARI", "GUCLU", "BILGI"].index(
                        cfg.get("min_severity", "KRITIK")),
                    key="tg_min_sev",
                    help="Bu seviye ve UZERI olaylar telefona push edilir")
                if st.button("💾 Telegram Ayarini Kaydet",
                              type="primary", use_container_width=True,
                              key="tg_save"):
                    new_cfg = {
                        "bot_token": bot_token.strip(),
                        "chat_id": chat_id.strip(),
                        "enabled": enabled,
                        "min_severity": min_sev,
                    }
                    if tg.save_config(new_cfg):
                        st.success("Ayar kaydedildi. Bundan sonra kritik "
                                    "haberler telefonuna gelir.")
                    else:
                        st.error("Kaydedilemedi - dosya yazma hatasi")
            except Exception as e:
                st.error(f"Telegram modulu yuklenemedi: {e}")

        # =================================================================
        # TELEFON / LAN ERISIM BILGISI
        # =================================================================
        with st.expander("📱 Telefon Uygulamasi (PWA + APK)", expanded=False):
            try:
                import socket
                import urllib.parse
                hostname = socket.gethostname()
                try:
                    from phone_app_server import _local_ip as _lan_ip
                    local_ip = _lan_ip()
                except Exception:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    local_ip = s.getsockname()[0]
                    s.close()
                pwa_url = f"http://{local_ip}:8502"
                dash_url = f"http://{local_ip}:8501"
                st.markdown(f"**Bilgisayar:** `{hostname}` · **IP:** `{local_ip}`")
                st.success(
                    f"**Telefon APP (onerilen):** [{pwa_url}]({pwa_url})\n\n"
                    "Chrome/Safari → **Ana ekrana ekle** → uygulama gibi acilir."
                )
                st.info(f"**Direkt dashboard:** [{dash_url}]({dash_url})")
                st.markdown(
                    "**Bildirimler:** Telegram (sidebar) — kritik olaylar telefona push. "
                    "APK kurulumu icin `APK_OLUSTURMA.md` dosyasina bak."
                )
                try:
                    qr_pwa = (
                        "https://api.qrserver.com/v1/create-qr-code/?"
                        f"size=200x200&data={urllib.parse.quote(pwa_url)}"
                    )
                    st.image(qr_pwa, caption="QR okut → Telefon APP (port 8502)", width=200)
                except Exception:
                    pass
                st.caption(
                    "Firewall: Allow access. Mobil veri icin ngrok/Tailscale gerekir. "
                    "EXE acikken 8501 (dashboard) + 8502 (PWA shell) dinlenir."
                )
            except Exception as e:
                st.caption(f"IP tespit edilemedi: {e}")

        st.divider()
        # HIA durumu + Supply Chain Risk Flasor
        st.markdown("### 🛰 Hardware Intel")
        try:
            age = cache_age_hours()
            stale = is_stale()
            intel = get_intel()
            if age is None:
                st.warning("HIA hic calistirilmadi")
            elif stale:
                st.warning(f"⚠️ Cache STALE ({age:.0f}h)")
            else:
                st.success(f"✅ Cache FRESH ({age:.1f}h)")

            # Kritik alarmlari kirmizi flasor
            geo = intel.get("geopolitics", {})
            crit = [t for t, g in geo.items()
                     if isinstance(g, dict) and g.get("critical_alert")]
            if crit:
                # CSS flashing animation
                st.markdown("""
                <style>
                @keyframes flash {
                  0% { background-color: #ff0000; opacity: 1; }
                  50% { background-color: #8b0000; opacity: 0.7; }
                  100% { background-color: #ff0000; opacity: 1; }
                }
                .flash-alert {
                  animation: flash 1.2s infinite;
                  padding: 10px;
                  border-radius: 8px;
                  color: white;
                  font-weight: bold;
                  text-align: center;
                  margin: 6px 0;
                }
                </style>
                """, unsafe_allow_html=True)
                st.markdown(
                    f'<div class="flash-alert">🚨 SUPPLY CHAIN RISK 🚨<br>'
                    f'{", ".join(crit)}</div>',
                    unsafe_allow_html=True)
            cycle = intel.get("semi_cycle", {})
            if cycle:
                st.caption(f"**Cycle:** {cycle.get('phase','?')[:24]}  "
                            f"({cycle.get('cycle_score',0)}/100)")
        except Exception as e:
            st.caption(f"HIA hata: {e}")

        st.divider()
        st.markdown("### 📡 Watchlist Manager")
        st.caption("Yeni semboller ekle (AXTI, NVTS, QUBT...). Otomatik durability "
                   "ve 10y CAGR analizi yapilir.")

        if "watchlist" not in st.session_state:
            st.session_state["watchlist"] = list(ALL_WATCHLIST_DEFAULTS)
        else:
            # Yeni eklenen AI/Kuantum hisselerini mevcut listeye otomatik ekle
            merged = list(st.session_state["watchlist"])
            for sym in ALL_WATCHLIST_DEFAULTS:
                if sym not in merged:
                    merged.append(sym)
            st.session_state["watchlist"] = merged

        new_t = st.text_input("Sembol", placeholder="orn: AXTI", key="wl_input")
        cc1, cc2 = st.columns(2)
        if cc1.button("➕ Ekle", use_container_width=True):
            if new_t.strip():
                tt = new_t.strip().upper()
                if tt not in st.session_state["watchlist"]:
                    # Hizli dogrulama
                    with st.spinner(f"{tt} kontrol ediliyor..."):
                        try:
                            df = fetch_history(tt, period="6mo")
                            if df.empty:
                                st.warning(f"{tt} icin veri bulunamadi.")
                            else:
                                st.session_state["watchlist"].append(tt)
                                st.success(f"{tt} eklendi.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"{tt}: {e}")
        if cc2.button("🗑️ Temizle", use_container_width=True):
            st.session_state["watchlist"] = []
            st.rerun()

        if st.session_state["watchlist"]:
            st.markdown("**Mevcut izleme listesi:**")
            for t in list(st.session_state["watchlist"]):
                ic1, ic2 = st.columns([3, 1])
                badge = ""
                if t in CHINA_TICKERS:
                    badge = " 🇨🇳"
                elif t == "ASML":
                    badge = " 🇳🇱"
                ic1.write(f"• `{t}`{badge}")
                if ic2.button("✕", key=f"rm_{t}"):
                    st.session_state["watchlist"].remove(t)
                    st.rerun()

        st.divider()
        st.markdown("### 📖 Master Score")
        st.markdown("- **85+** KRITIK ALIM 🚨\n- **70+** Guclu Al ✅\n"
                    "- **55+** Al 🟢\n- **40+** Bekle 🟡\n- **<40** Dikkat/Sat 🔴")
        st.divider()
        st.caption("Yatirim tavsiyesi degildir. Egitim amaclidir.")


# ===========================================================================
# Investor Executive Summary (en uste konulur)
# ===========================================================================

def render_investor_overview(results: dict):
    """Yatirimci icin TEK-BAKIS overview. Kullanici talebi: 4 sutun."""
    st.markdown("## 🏆 Investor Executive Summary")
    st.caption("Hisse & Vizyon  •  Stratejik Durum  •  10y Confidence Score  •  Verdict")
    st.caption("Apple piyasa degeri ($3.5T) hard ceiling | Lopez de Prado Purged CV "
                "ile overfitting korumasi | Fisher Scuttlebutt yontemiyle Ar-Ge "
                "yogun hisselerde kulis arastirmasi")

    try:
        df = build_investor_overview(results)
    except Exception as e:
        st.error(f"Overview olusturulamadi: {e}")
        return
    if df.empty:
        st.info("Henuz hisse analiz edilmedi.")
        return

    # Renkli verdict ile gosterimi
    def _color(v: str) -> str:
        c = get_verdict_color(v)
        return f"background-color:{c}; color:white; font-weight:bold; text-align:center"

    # v8 ana kolon seti (kullanici talebi):
    # Hisse | Stratejik Rol | Kritik Eşik | Master Score | Verdict
    # + Moonshot/Explosive/Confidence ek kolonlari
    main_cols = ["Hisse", "Stratejik Rol", "Kritik Esik",
                  "Master Score", "Verdict",
                  "10y Confidence Score", "Moonshot", "Explosive Factor"]
    styled = df[main_cols].style
    # pandas version uyumlulugu: yeni surumlerde Styler.map, eskilerde applymap
    if hasattr(styled, "map"):
        styled = styled.map(_color, subset=["Verdict"])
    else:
        styled = styled.applymap(_color, subset=["Verdict"])
    styled = styled.background_gradient(subset=["10y Confidence Score",
                                                 "Master Score"],
                                          cmap="RdYlGn", vmin=0, vmax=100)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Moonshot adaylari uyari panosu
    moon_rows = df[df["Moonshot"] == "🚀"]
    if not moon_rows.empty:
        st.caption("🚀 **Moonshot Candidates** (NVTS, INDI, RGTI): "
                   "J-Curve dedektoru ile Revenue/R&D paralel büyüme, "
                   "backlog patlaması ve gelir çarpanı izlenir. "
                   "Onaylı J-Curve = +20 Master Score 'Sıçrama Potansiyeli'.")

    # Sayilarin ozeti
    c1, c2, c3, c4, c5 = st.columns(5)
    counts = df["Verdict"].value_counts().to_dict()
    c1.metric("🟢 EKLE", counts.get("EKLE", 0))
    c2.metric("✅ TUT",  counts.get("TUT",  0))
    c3.metric("⏸️ BEKLE",counts.get("BEKLE",0))
    c4.metric("⚠️ AZALT",counts.get("AZALT",0))
    c5.metric("🚨 DIKKAT",counts.get("DIKKAT",0))

    # Foundry Capex korelasyon ozeti
    st.markdown("**Foundry Capex (TSM/INTC) Korelasyon - Sektorel Bagimlilik**")
    capex_view = df[["Hisse", "Stratejik Rol", "Foundry Capex Korelasyon",
                       "Capex Bagimliligi"]].copy()
    st.dataframe(capex_view, use_container_width=True, hide_index=True)

    # ---- MUHENDISLIK NOTU (v8 kullanici talebi) ----
    st.markdown("### 🛠️ Muhendislik Notu (Teknik Yorum)")
    st.caption("Her hisse icin donanim/teknoloji bilgi tabani + master score "
                "modifier'larina ve overlay'lere dayali dinamik durum yorumu.")
    # 2 kolon halinde
    items = list(results.items())
    for i in range(0, len(items), 2):
        c1, c2 = st.columns(2)
        for col, (t, r) in zip((c1, c2), items[i:i+2]):
            with col:
                note = get_engineering_note(t, r)
                if not note["base_note"]:
                    continue
                with st.container(border=True):
                    st.markdown(f"**`{t}` — Muhendislik Notu**")
                    st.caption(note["base_note"])
                    if note["dynamic_status"]:
                        st.markdown("**Durum:**")
                        for ds in note["dynamic_status"]:
                            st.markdown(f"- {ds}")
                    st.markdown(
                        f"**Kritik Esik:** _{note['critical_threshold']}_")


def render_executive_brief(results: dict):
    """Her hisse icin dogal dil yorum + aksiyon + genel piyasa ozeti."""
    st.markdown("## 🧠 Yorum & Aksiyon Paneli")
    st.caption("Her hisse icin Master Score breakdown'i, modifier'lari ve "
                "stratejik overlay'i okuyarak rule-based dogal dil yorum + "
                "aksiyon onerisi uretir.")

    briefs = [brief_for_ticker(r) for r in results.values()]
    briefs = sorted(briefs, key=lambda b: -b.get("master_score", 0))

    # ---- PIYASA OZETI (en uste) ----
    summary = market_summary(briefs)
    st.markdown(f"### {summary['regime_text']}")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Hisse sayisi", summary["n_tickers"])
    c2.metric("Ortalama Master", f"{summary['avg_master_score']:.1f}")
    c3.metric("Ort. 10y Confidence",
                f"{summary['avg_confidence_10y']:.0f}/100")
    c4.metric("🟢 EKLE", summary["counts"].get("EKLE", 0))
    c5.metric("✅ TUT",  summary["counts"].get("TUT", 0))
    c6.metric("🚨 DIKKAT", summary["counts"].get("DIKKAT", 0)
                + summary["counts"].get("AZALT", 0))
    if summary.get("strongest"):
        s = summary["strongest"]; w = summary["weakest"]
        st.caption(
            f"**En guclu:** `{s['ticker']}` {s['master_score']:.0f} "
            f"({s['verdict']})   |   "
            f"**En zayif:** `{w['ticker']}` {w['master_score']:.0f} "
            f"({w['verdict']})"
        )

    st.divider()

    # ---- HISSE BAZLI BRIEF KARTLARI ----
    verdict_color = {
        "EKLE":   "#00c853", "TUT": "#64dd17", "BEKLE": "#ffc107",
        "AZALT":  "#ff6e40", "DIKKAT": "#d50000",
    }
    for b in briefs:
        col_c = verdict_color.get(b["verdict"], "#888")
        with st.container(border=True):
            top1, top2, top3 = st.columns([3, 1, 1])
            with top1:
                st.markdown(
                    f"### `{b['ticker']}` — "
                    f"<span style='color:{col_c};font-weight:bold;'>"
                    f"{b['verdict']}</span>",
                    unsafe_allow_html=True)
                st.caption(f"Rating: {b['rating']}")
            with top2:
                st.metric("Master", f"{b['master_score']:.1f}")
            with top3:
                st.metric("10y Conf.", f"{b['confidence_10y']:.0f}")

            st.markdown(b["summary"])

            colL, colR = st.columns(2)
            with colL:
                if b["opportunities"]:
                    st.markdown("**✨ Firsatlar / Katalistler:**")
                    for o in b["opportunities"]:
                        st.markdown(f"- {o}")
                else:
                    st.caption("• Belirgin pozitif katalist yok.")
            with colR:
                if b["risks"]:
                    st.markdown("**⚠️ Riskler:**")
                    for rk in b["risks"]:
                        st.markdown(f"- {rk}")
                else:
                    st.caption("• Belirgin risk yok.")

            st.success(f"**Aksiyon:** {b['action']}")


# ===========================================================================
# Portfoy sekmesi (Black-Litterman)
# ===========================================================================

def render_portfolio(results: dict):
    """Black-Litterman ile yatirimci-gorus-tabanli portfoy optim."""
    st.markdown("## 💼 Portfoy Optimizasyonu (Black-Litterman)")
    st.caption("Mean-Variance optimization'un (Markowitz) ekstrem agirlik "
                "problemini cozmek icin Black-Litterman modeli kullanilir. "
                "Senin kendi gorusunu (Orn: 'ATOM lisanslama yapacak') "
                "matematiksel modele dahil eder.")

    histories = {t: r["df"] for t, r in results.items()
                  if r.get("df") is not None and not r["df"].empty}
    if len(histories) < 2:
        st.warning("En az 2 hisse gerekli.")
        return

    # Market caps - fundamental verilerden cek
    market_caps = {}
    for t, r in results.items():
        mc = (r.get("fundamental", {}) or {}).get("market_cap", 0)
        market_caps[t] = mc if mc > 0 else 1.0

    # Investor view sayisini kullanicidan al
    st.markdown("### 🧠 Yatirimci Gorusleri (Investor Views)")
    st.caption("Bos birakirsan piyasa dengesi (implied returns) kullanilir.")

    if "investor_views" not in st.session_state:
        st.session_state["investor_views"] = []

    with st.form("view_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            vt = st.selectbox("Hisse", list(histories.keys()), key="view_ticker")
        with col2:
            er = st.number_input("Yillik Beklenen Getiri %",
                                   min_value=-50.0, max_value=200.0,
                                   value=15.0, step=1.0)
        with col3:
            conf = st.slider("Guven (0=zayif, 1=tam)", 0.0, 1.0, 0.5, 0.05)
        if st.form_submit_button("➕ Gorus Ekle"):
            st.session_state["investor_views"].append({
                "ticker": vt, "expected_annual_return": er / 100.0,
                "confidence": conf,
            })

    # Mevcut gorus listesi
    if st.session_state["investor_views"]:
        st.markdown("**Aktif Gorusler:**")
        for i, v in enumerate(st.session_state["investor_views"]):
            c1, c2 = st.columns([6, 1])
            c1.write(f"`{v['ticker']}` -> %{v['expected_annual_return']*100:.0f} yillik  "
                       f"(guven %{v['confidence']*100:.0f})")
            if c2.button("Sil", key=f"del_view_{i}"):
                st.session_state["investor_views"].pop(i)
                st.rerun()
        if st.button("Tum Goruslerimi Sil"):
            st.session_state["investor_views"] = []
            st.rerun()

    # Optimum portfoy hesapla
    st.markdown("### 📊 Optimum Portfoy")
    risk_av = st.slider("Risk Aversiyonu (1=agresif, 5=muhafazakar)",
                          1.0, 5.0, 2.5, 0.25)
    with st.spinner("Black-Litterman cozumu..."):
        try:
            out = portfolio_optimization(
                histories, market_caps,
                views=st.session_state["investor_views"],
                risk_aversion=risk_av,
            )
        except Exception as e:
            st.error(f"Optim hatasi: {e}")
            return

    if "error" in out:
        st.error(out["error"])
        return

    # Sonuc tablo
    w = out["weights"] * 100
    prior = out["prior_returns_pct"]
    post = out["posterior_returns_pct"]
    hist = out["historical_returns_pct"]
    table = pd.DataFrame({
        "Hisse": w.index,
        "Tarihsel Yillik %":  hist.values,
        "Prior (Piyasa) %":    prior.values,
        "Posterior (Goruslu) %": post.values,
        "Optimum Agirlik %": w.values,
    }).round(2).sort_values("Optimum Agirlik %", ascending=False)
    st.dataframe(table, use_container_width=True, hide_index=True,
                  column_config={
                      "Optimum Agirlik %": st.column_config.ProgressColumn(
                          "Optimum Agirlik %", min_value=0, max_value=100,
                          format="%.1f%%"),
                  })

    # Ozet metrikleri
    c1, c2, c3 = st.columns(3)
    c1.metric("Beklenen Yillik Getiri",
                f"%{out['expected_portfolio_return_pct']:.1f}")
    c2.metric("Beklenen Volatilite",
                f"%{out['expected_portfolio_vol_pct']:.1f}")
    c3.metric("Sharpe Ratio", f"{out['sharpe_ratio']:.2f}",
                "yuksek=iyi" if out['sharpe_ratio'] >= 1 else "dusuk")

    # Pie chart
    try:
        import plotly.express as px
        w_disp = w[w > 1].sort_values(ascending=False)
        if not w_disp.empty:
            fig = px.pie(values=w_disp.values, names=w_disp.index,
                          title="Portfoy Dagilimi (>%1 olan hisseler)",
                          color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_layout(template="plotly_dark", height=380,
                               paper_bgcolor="#0e1117")
            st.plotly_chart(fig, use_container_width=True, key="portfolio_pie")
    except Exception as e:
        st.caption(f"Pasta grafik hatasi: {e}")


# ===========================================================================
# Sanal Portfoy (Paper Trading) - kullanici talebi: her hisseye $1000
# ===========================================================================

def render_paper_portfolio(results: dict):
    """
    Her hisseye sabit USD yatirim simulasyonu. Baslangic fiyati
    kilitlenir; bugunden itibaren canli toplam deger izlenir.
    """
    import paper_portfolio as pp

    st.markdown("## 💸 Sanal Portfoy Simulasyonu")
    st.caption("Her hisseye bugunden itibaren sabit miktar yatir, "
                "baslangic fiyati kilitlenir. **Toplam degerin nasil "
                "evrildigini canli takip et.**")

    state = pp.get_state()
    is_init = bool(state and state.get("positions"))

    # ---- INIT KONTROL PANELI ----
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            per_usd = st.number_input(
                "Hisse basina yatirim ($)", min_value=100.0, max_value=100_000.0,
                value=float(state.get("per_ticker_usd", 1000.0)) if state else 1000.0,
                step=100.0,
                key="paper_per_usd")
        with c2:
            st.write("")  # spacer
            if not is_init:
                if st.button("🚀 Simulasyonu Baslat", use_container_width=True,
                              type="primary"):
                    with st.spinner("Baslangic fiyatlari kilitleniyor..."):
                        pp.initialize(list(results.keys()),
                                       per_ticker_usd=per_usd)
                    st.rerun()
            else:
                if st.button("➕ Yeni Hisseleri Ekle", use_container_width=True):
                    with st.spinner("Yeni hisseler ekleniyor..."):
                        pp.initialize(list(results.keys()),
                                       per_ticker_usd=per_usd)
                    st.rerun()
        with c3:
            st.write("")
            if is_init and st.button("🗑️ Sifirla", use_container_width=True):
                pp.reset()
                st.rerun()

    if not is_init:
        st.info("Henuz baslatilmadi. Her hisseye yatiracagin miktari sec ve "
                "yukaridan **'Simulasyonu Baslat'** butonuna tikla. Hisse "
                "fiyatlari **simdiki** anda kilitlenir, ilerideki degisim "
                "buradan canli takip edilir.")
        return

    # ---- ANLIK DEGER ----
    # Histories'i recycle et - hem hizli hem cache hit
    quotes = {}
    histories = {}
    for t, r in results.items():
        df = r.get("df")
        if df is not None and not df.empty:
            quotes[t] = float(df["Close"].iloc[-1])
            histories[t] = df

    val = pp.current_value(state=pp.get_state(), quotes=quotes)
    total_inv = val["total_invested"]
    total_val = val["total_value"]
    total_pnl = val["total_pnl"]
    total_pct = val["total_pnl_pct"]
    per = val["per_ticker"]
    created = val.get("created_at", "-")

    color = "#00c853" if total_pnl >= 0 else "#ff1744"
    sign = "+" if total_pnl >= 0 else ""

    st.markdown(
        f"<div style='background:linear-gradient(90deg,#1a1d24,{color}22);"
        f"padding:18px;border-radius:10px;border-left:6px solid {color};"
        f"margin:10px 0;'>"
        f"<div style='font-size:14px;color:#999;'>Toplam Yatirilan "
        f"(baslangic: {created[:10]}) · {len(per)} hisse</div>"
        f"<div style='font-size:30px;font-weight:bold;'>"
        f"${total_inv:,.0f} → <span style='color:{color};'>${total_val:,.2f}</span></div>"
        f"<div style='font-size:18px;color:{color};'>"
        f"K/Z: {sign}${total_pnl:,.2f}  ({sign}{total_pct:.2f}%)</div>"
        "</div>", unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Hisse Sayisi", len(per))
    m2.metric("Gun (tutulan)", max((p["days_held"] for p in per.values()), default=0))
    best = max(per.items(), key=lambda x: x[1]["pnl_pct"], default=(None, {}))
    worst = min(per.items(), key=lambda x: x[1]["pnl_pct"], default=(None, {}))
    if best[0]:
        m3.metric("En Iyi", f"{best[0]} {best[1]['pnl_pct']:+.1f}%")
    if worst[0]:
        m4.metric("En Kotu", f"{worst[0]} {worst[1]['pnl_pct']:+.1f}%")

    # ---- HISSE BAZLI TABLO ----
    rows = []
    for t, p in per.items():
        rows.append({
            "Hisse":         t,
            "Yatirilan":     f"${p['invested']:,.0f}",
            "Adet":          f"{p['shares']:.4f}",
            "Baslangic":     f"${p['start_price']:.2f}",
            "Anlik":         f"${p['current_price']:.2f}",
            "Deger":         f"${p['value']:,.2f}",
            "K/Z $":         f"${p['pnl']:+,.2f}",
            "K/Z %":         f"{p['pnl_pct']:+.2f}%",
            "Gun":           p["days_held"],
        })
    df_paper = pd.DataFrame(rows)

    # Renkli K/Z kolonu
    def _color_pnl(v):
        try:
            num = float(str(v).replace("$", "").replace(",", "")
                              .replace("%", "").replace("+", ""))
            if num > 0:
                return "color:#00c853;font-weight:bold"
            if num < 0:
                return "color:#ff1744;font-weight:bold"
        except Exception:
            pass
        return ""
    sty = df_paper.style
    if hasattr(sty, "map"):
        sty = sty.map(_color_pnl, subset=["K/Z $", "K/Z %"])
    else:
        sty = sty.applymap(_color_pnl, subset=["K/Z $", "K/Z %"])
    st.dataframe(sty, use_container_width=True, hide_index=True)

    # ---- CANLI GRAFIK (bugun basladiysa bile dolu) ----
    st.markdown("### 📈 Portfoy Degeri — Canli")
    st.caption("Baslangic anindan bugune: portfoyun, yatirilan tutarin ve "
                "**SPY (S&P500)** karsilastirmasi.")
    try:
        with st.spinner("Canli grafik hazirlaniyor..."):
            ts = pp.live_value_series(state=pp.get_state(),
                                       quotes=quotes, histories=histories)
        if ts.empty:
            st.info("Grafik verisi olusturulamadi.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=ts.index, y=ts["portfoy_value"],
                name="Senin Portfoyun", mode="lines+markers",
                line=dict(width=3, color="#00c853" if total_pnl >= 0 else "#ff8a65"),
                marker=dict(size=6),
                fill="tozeroy", fillcolor="rgba(0,200,83,0.08)"))
            fig.add_trace(go.Scatter(
                x=ts.index, y=ts["invested"],
                name="Yatirilan ($)", mode="lines",
                line=dict(dash="dash", color="#888", width=2)))
            if "spy_benchmark" in ts.columns:
                fig.add_trace(go.Scatter(
                    x=ts.index, y=ts["spy_benchmark"],
                    name="SPY (esit $1000/hisse)", mode="lines",
                    line=dict(dash="dot", color="#42a5f5", width=2)))
            # K/Z fark metrigi
            if len(ts) >= 1:
                last = ts.iloc[-1]
                spy_last = last.get("spy_benchmark", total_inv)
                alpha = total_val - float(spy_last)
                st.caption(
                    f"**Alpha (portfoy - SPY):** "
                    f"${alpha:+,.2f}  |  Son nokta: "
                    f"Portfoy ${last['portfoy_value']:,.2f} vs "
                    f"SPY ${float(spy_last):,.2f}")
            fig.update_layout(
                template="plotly_dark", height=450,
                paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                margin=dict(l=20, r=20, t=20, b=20),
                yaxis_title="USD", xaxis_title="Tarih",
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
                hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, key="paper_value_ts")
    except Exception as e:
        st.warning(f"Grafik hatasi: {e}")

    # ---- GELECEK SENARYOLARI (gercekci, hisse-bazli) ----
    st.markdown("### 🔮 Gelecek Senaryolari — Gercekci Model")
    st.caption("Her hisse **kendi sektor CAGR'i** ile projekte edilir. "
                "Spekulatif hisselere basari olasiligi <100% uygulanir, "
                "ve **20x global hard cap** ile her hisse ozel cap "
                "(orn. NVTS $100) zorlanir.")
    try:
        sc = pp.portfolio_scenarios(state=pp.get_state(), quotes=quotes)
        sc_rows = []
        inv = sc["current"]["invested"]
        for horizon, data in sc["scenarios"].items():
            yrs = data["years"]
            for label, key, emoji in [
                ("Kotumser", "pessimistic", "🔴"),
                ("Temel",    "base",        "🟡"),
                ("Iyimser",  "optimistic",  "🟢"),
            ]:
                fv = data[key]
                pnl = fv - inv
                pct = pnl / inv * 100 if inv > 0 else 0
                cagr_eff = ((fv/inv)**(1/yrs)-1)*100 if inv > 0 and fv > 0 else 0
                sc_rows.append({
                    "Vade": horizon.upper(),
                    "Senaryo": f"{emoji} {label}",
                    "Tahmini Deger": f"${fv:,.0f}",
                    "K/Z $": f"${pnl:+,.0f}",
                    "K/Z %": f"{pct:+.1f}%",
                    "CAGR (etkin)": f"%{cagr_eff:.1f}",
                })
        st.dataframe(pd.DataFrame(sc_rows), use_container_width=True, hide_index=True)

        # Senaryo bar chart (10y)
        if "10y" in sc["scenarios"]:
            d10 = sc["scenarios"]["10y"]
            fig_sc = go.Figure(go.Bar(
                x=["Kotumser", "Temel", "Iyimser"],
                y=[d10["pessimistic"], d10["base"], d10["optimistic"]],
                marker_color=["#ff1744", "#ffc107", "#00c853"],
                text=[f"${v:,.0f}" for v in
                      [d10["pessimistic"], d10["base"], d10["optimistic"]]],
                textposition="outside"))
            fig_sc.add_hline(y=inv, line_dash="dash", line_color="#888",
                              annotation_text=f"Yatirilan: ${inv:,.0f}")
            fig_sc.update_layout(
                template="plotly_dark", height=320,
                title="10 Yil Senaryo — Portfoy Degeri",
                paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                yaxis_title="USD", showlegend=False,
                margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_sc, use_container_width=True, key="paper_scenario_10y")

        # Hisse-bazli 10y dagilim (Base senaryo)
        per10 = (sc.get("per_ticker_10y") or {}).get("base", {})
        if per10:
            with st.expander("📊 Hisse-bazli 10Y Base Senaryo Detayi"):
                df_per = pd.DataFrame([
                    {"Hisse": t,
                      "CAGR % (hisse)":   d["cagr_pct"],
                      "Basari Olasiligi": d["p_success"],
                      "10Y Beklenen $":   d["future_val"]}
                    for t, d in per10.items()
                ]).sort_values("10Y Beklenen $", ascending=False)
                st.dataframe(df_per, use_container_width=True, hide_index=True)

        # Notlar
        with st.expander("ℹ️ Model varsayimlari"):
            for n in sc.get("notes", []):
                st.caption(f"• {n}")
    except Exception as e:
        st.warning(f"Senaryo hatasi: {e}")

    # ---- AYLIK DCA PROJEKSIYONU ----
    st.markdown("### 💵 Aylik DCA Projeksiyonu")
    # Portfoy bilesimine gore dinamik getiri onerisi
    try:
        suggested_return = pp.suggest_dca_return(state=pp.get_state(), quotes=quotes)
    except Exception:
        suggested_return = 6.0
    st.caption(f"Simdi baslattigin portfoye **her ay ek yatirim** yaparsan "
                f"ileride toplam ne olur? Mevcut bilesim icin "
                f"**onerilen yillik getiri: %{suggested_return:.1f}** "
                f"(senaryo modelindeki 10y BASE etkin CAGR).")
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        monthly_add = st.number_input("Aylik ek yatirim ($)", 0.0, 50_000.0,
                                      500.0, 100.0, key="paper_dca_monthly")
    with dc2:
        dca_months = st.slider("Kac ay ileri?", 3, 60, 24, key="paper_dca_months")
    with dc3:
        dca_return = st.slider("Beklenen yillik getiri %", -10.0, 30.0,
                                float(suggested_return), 0.5,
                                key="paper_dca_return",
                                help="Senaryo modelinden gelen oneri; "
                                     "manuel ayarlanabilir.")
    try:
        dca_df = pp.dca_projection(monthly_usd=monthly_add,
                                    months=dca_months,
                                    annual_return_pct=dca_return)
        if not dca_df.empty:
            fig_dca = go.Figure()
            fig_dca.add_trace(go.Scatter(
                x=dca_df["tarih"], y=dca_df["deger"],
                name="Portfoy Degeri (projeksiyon)", mode="lines+markers",
                line=dict(color="#00c853", width=3)))
            fig_dca.add_trace(go.Scatter(
                x=dca_df["tarih"], y=dca_df["yatirilan"],
                name="Toplam Yatirilan", mode="lines",
                line=dict(dash="dash", color="#888")))
            fig_dca.update_layout(
                template="plotly_dark", height=360,
                paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                yaxis_title="USD", hovermode="x unified",
                margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_dca, use_container_width=True, key="paper_dca_chart")
            last = dca_df.iloc[-1]
            st.success(
                f"**{dca_months} ay sonra:** Yatirilan ${last['yatirilan']:,.0f}  →  "
                f"Deger ${last['deger']:,.0f}  ({last['k_z_pct']:+.1f}%)")
    except Exception as e:
        st.caption(f"DCA projeksiyon hatasi: {e}")

    # ---- OTOMATIK YENILEME BILGISI ----
    st.caption(f"⏱️ Otomatik yenileme: her **{REFRESH_MINUTES} dk** "
                f"(sidebar). Son guncelleme: "
                f"{datetime.now().strftime('%H:%M:%S')}")

    # ---- HISSE BAZLI K/Z BAR GRAFIK ----
    try:
        df_bar = pd.DataFrame([
            {"Hisse": t, "K/Z $": p["pnl"], "K/Z %": p["pnl_pct"]}
            for t, p in per.items()
        ]).sort_values("K/Z %", ascending=False)
        fig2 = px.bar(df_bar, x="Hisse", y="K/Z %", text="K/Z %",
                       color="K/Z %", color_continuous_scale="RdYlGn",
                       color_continuous_midpoint=0)
        fig2.update_layout(template="plotly_dark", height=330,
                            paper_bgcolor="#0e1117", plot_bgcolor="#1a1d24",
                            yaxis_title="K/Z %", showlegend=False,
                            margin=dict(l=20, r=20, t=20, b=20))
        fig2.update_traces(texttemplate="%{text:+.2f}%", textposition="outside")
        st.plotly_chart(fig2, use_container_width=True, key="paper_pnl_bar")
    except Exception as e:
        st.caption(f"Bar grafik hatasi: {e}")


# ===========================================================================
# Main
# ===========================================================================

def main():
    sidebar()

    st.title("🚀 Quant AI Dashboard v8 - Investor Executive Summary")
    st.caption("Yari Iletken + Kuantum Takip Istasyonu | "
                "Apple Market Cap Hard Ceiling | "
                "Lopez de Prado Purged CV + MDA | "
                "Fisher Scuttlebutt Researcher | "
                "Black-Litterman Portfoy Optimizasyonu")
    st.caption(f"🇺🇸 Cekirdek: {' · '.join(TICKERS)}   |   "
               f"🌐 Global Watchlist: {', '.join(st.session_state.get('watchlist', [])) or '-'}   |   "
               f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Cekirdek hisseler
    with st.spinner("Fiyat verileri cekiliyor..."):
        histories = cached_all_histories(tuple(TICKERS))
    if not histories:
        st.error("Veri alinamadi. Internet baglantisi veya yfinance erisimini kontrol et.")
        return

    with st.spinner("Sentiment + Temel + ML + Master Score..."):
        results = {}
        for t in TICKERS:
            if t in histories:
                try:
                    results[t] = analyze_ticker(t, histories[t])
                except Exception as e:
                    logger.error("analyze %s: %s", t, e)
                    st.warning(f"{t} analizi atlandi: {e}")

    if not results:
        st.error("Hicbir hisse analiz edilemedi.")
        return

    # --- INVESTOR OVERVIEW (en uste, tabbed icerigin ustunde) ---
    try:
        render_investor_overview(results)
    except Exception as e:
        st.error(f"Investor Overview hatasi: {e}")
    st.divider()

    # --- YORUM & AKSIYON PANELI (kullanici talebi - dogal dil yorum) ---
    try:
        render_executive_brief(results)
    except Exception as e:
        st.error(f"Yorum paneli hatasi: {e}")
    st.divider()

    tabs = st.tabs([
        "💸 Sanal Portfoy",
        "🎯 Ozet", "📊 Detay", "🌟 Vision", "💼 Portfoy", "🛰 HIA", "🔬 Research",
        "🏭 Sektorel Zeka", "📈 Backtest", "🔮 Forecast", "💰 Temel",
        "📡 Radar", "📅 Milestone", "💵 DCA", "📋 Loglar",
    ])

    with tabs[0]:
        try: render_paper_portfolio(results)
        except Exception as e: st.error(f"Sanal Portfoy hatasi: {e}")
    with tabs[1]:
        try: render_overview(results)
        except Exception as e: st.error(f"Ozet hatasi: {e}")
    with tabs[2]:
        try: render_detail(results)
        except Exception as e: st.error(f"Detay hatasi: {e}")
    with tabs[3]:
        try: render_vision(results)
        except Exception as e: st.error(f"Vision hatasi: {e}")
    with tabs[4]:
        try: render_portfolio(results)
        except Exception as e: st.error(f"Portfoy hatasi: {e}")
    with tabs[5]:
        try: render_hardware_intel(results)
        except Exception as e: st.error(f"HIA hatasi: {e}")
    with tabs[6]:
        try: render_research_agent(results)
        except Exception as e: st.error(f"Research Agent hatasi: {e}")
    with tabs[7]:
        try:
            histories_for_sector = {t: r["df"] for t, r in results.items()
                                      if r.get("df") is not None}
            render_sector(results, histories_for_sector)
        except Exception as e:
            st.error(f"Sektorel Zeka hatasi: {e}")
    with tabs[8]:
        try: render_backtest(results)
        except Exception as e: st.error(f"Backtest hatasi: {e}")
    with tabs[9]:
        try: render_forecast(results)
        except Exception as e: st.error(f"Forecast hatasi: {e}")
    with tabs[10]:
        try: render_fundamentals(results)
        except Exception as e: st.error(f"Temel analiz hatasi: {e}")
    with tabs[11]:
        try: render_radar(results)
        except Exception as e: st.error(f"Radar hatasi: {e}")
    with tabs[12]:
        try: render_milestones(results)
        except Exception as e: st.error(f"Milestone hatasi: {e}")
    with tabs[13]:
        try: render_dca(results)
        except Exception as e: st.error(f"DCA hatasi: {e}")
    with tabs[14]:
        try: render_logs()
        except Exception as e: st.error(f"Log hatasi: {e}")

    if st.session_state.get("auto_refresh", True):
        import streamlit.components.v1 as components
        ms = REFRESH_MINUTES * 60 * 1000
        next_run = datetime.now() + timedelta(minutes=REFRESH_MINUTES)
        st.sidebar.caption(f"Sonraki yenileme: ~{next_run.strftime('%H:%M')}")
        components.html(
            f"<script>setTimeout(function(){{window.parent.location.reload();}}, {ms});</script>",
            height=0,
        )


if __name__ == "__main__":
    main()
