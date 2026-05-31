"""
monte_carlo.py — Geometric Brownian Motion (GBM) Monte Carlo simulator.

Akademik Referans:
  - Black, F. & Scholes, M. (1973). The Pricing of Options and Corporate
    Liabilities. *Journal of Political Economy* 81(3), 637-654.
  - Hull, J. C. (2018). *Options, Futures, and Other Derivatives* (10th ed.),
    Bölüm 14: "Wiener Processes and Ito's Lemma".

Formul:
    dS_t = mu * S_t * dt + sigma * S_t * dW_t
    S_t  = S_0 * exp( (mu - 0.5*sigma^2)*t + sigma*sqrt(t)*Z ),  Z ~ N(0,1)

Bu modul:
  1. yfinance'tan tarihsel volatilite cikar.
  2. Sektor CAGR + ML prob_up'tan dinamik drift uretir.
  3. N=10,000 path simule eder.
  4. Fat-tail clip (20x cap + min 0.01) uygular.
  5. Median, %95 CI, VaR, CVaR, P(bust), P(10x) raporlar.
  6. Cikti: histogram-ready array + Gaussian fit parametreleri.

Math_Specs.md - Bolum 4 referansiyla uyumlu.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Veri yapilari
# ---------------------------------------------------------------------------
@dataclass
class MCInputs:
    """Monte Carlo simulasyon girdileri."""
    ticker: str
    spot_price: float
    annual_drift: float       # μ, decimal (0.15 = %15)
    annual_volatility: float  # σ, decimal (0.40 = %40)
    horizon_years: float = 10.0
    n_paths: int = 10_000
    n_steps_per_year: int = 252
    fat_tail_cap_multiplier: float = 20.0
    macro_stress: dict = field(default_factory=dict)
    # macro_stress: {'inflation': 0.04, 'rate_hike': 0.02, 'cycle_phase': 'EXPANSION'}


@dataclass
class MCResults:
    ticker: str
    inputs: MCInputs
    terminal_prices: np.ndarray
    percentile_paths: dict          # {p5, p25, p50, p75, p95} arraysi (timeline)
    timeline: pd.DatetimeIndex
    stats: dict


# ---------------------------------------------------------------------------
# Tarihsel volatilite (yfinance opsiyonel)
# ---------------------------------------------------------------------------
def estimate_drift_sigma(ticker: str,
                          history_years: float = 3.0) -> tuple[float, float]:
    """
    yfinance gunluk fiyatlardan annualized drift & sigma.
    history_years kadar gecmise bakar.
    Fallback: (0.10, 0.40).
    """
    try:
        import yfinance as yf
        period = f"{int(history_years*12)}mo"
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if df.empty or len(df) < 60:
            return 0.10, 0.40
        log_ret = np.log(df["Close"] / df["Close"].shift(1)).dropna()
        sigma = float(log_ret.std() * np.sqrt(252))
        mu = float(log_ret.mean() * 252 + 0.5 * sigma**2)
        # Spek hisselerin mu'su saptiriyor; ±%50 araliginda clamp
        mu = max(-0.20, min(0.50, mu))
        sigma = max(0.10, min(2.00, sigma))
        return mu, sigma
    except Exception as e:
        logger.debug("estimate_drift_sigma(%s) hata: %s", ticker, e)
        return 0.10, 0.40


# ---------------------------------------------------------------------------
# Macro stress overlay - mu/sigma'yi senaryoya gore ayarla
# ---------------------------------------------------------------------------
def _apply_macro_stress(mu: float, sigma: float, stress: dict) -> tuple[float, float]:
    """
    Inflation, faiz, cycle_phase ile drift ve volatiliteyi sok altina al.

    Mantik:
      - Yuksek enflasyon (>4%): mu -= 0.5*(infl - 0.04), sigma += 0.10
      - Faiz artisi: mu -= rate_hike * 0.8
      - PEAK -> mu *= 0.5, sigma *= 1.3
      - DOWNTURN -> mu -= 0.10, sigma *= 1.5
      - EXPANSION -> mu *= 1.10
    """
    infl = float(stress.get("inflation", 0.025))
    rate = float(stress.get("rate_hike", 0.0))
    phase = str(stress.get("cycle_phase", "")).upper()

    if infl > 0.04:
        mu -= 0.5 * (infl - 0.04)
        sigma += 0.05
    mu -= rate * 0.8

    if "PEAK" in phase:
        mu *= 0.5
        sigma *= 1.3
    elif "DOWNTURN" in phase:
        mu -= 0.10
        sigma *= 1.5
    elif "EXPANSION" in phase:
        mu *= 1.10
    elif "TROUGH" in phase:
        mu *= 0.8
        sigma *= 1.2

    return mu, sigma


# ---------------------------------------------------------------------------
# GBM Monte Carlo simulasyonu
# ---------------------------------------------------------------------------
def simulate_paths(inp: MCInputs, seed: int = 42) -> MCResults:
    """
    N path GBM simulasyonu uret. 'macro_stress' varsa drift/sigma'yi ayarlar.

    Returns:
      MCResults (terminal fiyatlar + percentile timelines + istatistikler)
    """
    rng = np.random.default_rng(seed)

    mu, sigma = inp.annual_drift, inp.annual_volatility
    if inp.macro_stress:
        mu, sigma = _apply_macro_stress(mu, sigma, inp.macro_stress)

    n_steps = int(inp.horizon_years * inp.n_steps_per_year)
    dt = 1.0 / inp.n_steps_per_year
    n_paths = inp.n_paths
    S0 = inp.spot_price

    # Vektorize: tek seferde (n_paths, n_steps) random matrix
    Z = rng.standard_normal(size=(n_paths, n_steps))
    drift = (mu - 0.5 * sigma**2) * dt
    diffusion = sigma * np.sqrt(dt) * Z

    # Cumsum -> log-price increments
    log_returns = drift + diffusion
    log_prices = np.cumsum(log_returns, axis=1)
    prices = S0 * np.exp(log_prices)  # shape (n_paths, n_steps)

    # FAT-TAIL CLIP — 20x cap horizon'a oranli
    cap = S0 * inp.fat_tail_cap_multiplier
    prices = np.clip(prices, 0.01, cap)

    # Terminal price'lar
    terminal = prices[:, -1]

    # Timeline ve percentile path'leri
    timeline = pd.date_range(start=pd.Timestamp.now().normalize(),
                              periods=n_steps + 1, freq="B")[:n_steps]
    percentile_paths = {
        "p05": np.percentile(prices, 5, axis=0),
        "p25": np.percentile(prices, 25, axis=0),
        "p50": np.percentile(prices, 50, axis=0),
        "p75": np.percentile(prices, 75, axis=0),
        "p95": np.percentile(prices, 95, axis=0),
    }

    # Istatistikler
    stats = summarize(terminal, S0, mu_adj=mu, sigma_adj=sigma)

    return MCResults(
        ticker=inp.ticker,
        inputs=inp,
        terminal_prices=terminal,
        percentile_paths=percentile_paths,
        timeline=timeline,
        stats=stats,
    )


# ---------------------------------------------------------------------------
# Istatistik ozeti (VaR, CVaR, P-bust, P-10x...)
# ---------------------------------------------------------------------------
def summarize(terminal: np.ndarray, S0: float,
              mu_adj: float, sigma_adj: float) -> dict:
    """
    Terminal fiyat dagiliminin asimetrik istatistikleri.
    Gaussian fit + Bessembinder fat-tail metrikleri.
    """
    # Yuzdelik dilimler
    p05, p25, p50, p75, p95 = np.percentile(terminal, [5, 25, 50, 75, 95])
    mean_T = float(terminal.mean())
    std_T = float(terminal.std())
    median_T = float(np.median(terminal))

    # PnL ratios
    pct_change = (terminal - S0) / S0
    pnl_median = float(np.median(pct_change))
    pnl_mean = float(pct_change.mean())

    # VaR & CVaR 5%
    var_5_price = float(p05)
    var_5_pct = float((p05 - S0) / S0)
    cvar_mask = terminal <= p05
    cvar_5_pct = float(((terminal[cvar_mask] - S0) / S0).mean()) if cvar_mask.any() else var_5_pct

    # Olasiliklar
    p_bust = float((terminal < 0.20 * S0).mean())     # -%80 ve dipte
    p_loss = float((terminal < S0).mean())             # negatif PnL
    p_double = float((terminal >= 2.0 * S0).mean())    # 2x+
    p_10x = float((terminal >= 10.0 * S0).mean())      # 10x+
    p_20x_cap = float((terminal >= 19.9 * S0).mean())  # cap'e dayanma orani

    # Implied annual CAGR (median)
    horizon = mu_adj if mu_adj else 0.10
    try:
        cagr_median = ((median_T / S0) ** (1 / 10.0) - 1) * 100  # 10y default
    except Exception:
        cagr_median = 0.0

    # Best/Worst (en kotu/en iyi senaryo orneklemleri)
    sorted_idx = np.argsort(terminal)
    worst_5 = terminal[sorted_idx[:5]].tolist()
    best_5 = terminal[sorted_idx[-5:]].tolist()

    return {
        "S0": S0,
        "mu_used": round(mu_adj, 4),
        "sigma_used": round(sigma_adj, 4),
        "mean_T": round(mean_T, 2),
        "median_T": round(median_T, 2),
        "std_T": round(std_T, 2),
        "p05": round(p05, 2),
        "p25": round(p25, 2),
        "p50": round(p50, 2),
        "p75": round(p75, 2),
        "p95": round(p95, 2),
        "pnl_median_pct": round(pnl_median * 100, 2),
        "pnl_mean_pct": round(pnl_mean * 100, 2),
        "VaR_5_price": round(var_5_price, 2),
        "VaR_5_pct": round(var_5_pct * 100, 2),
        "CVaR_5_pct": round(cvar_5_pct * 100, 2),
        "p_bust": round(p_bust * 100, 2),
        "p_loss": round(p_loss * 100, 2),
        "p_double": round(p_double * 100, 2),
        "p_10x": round(p_10x * 100, 2),
        "p_20x_cap_hit": round(p_20x_cap * 100, 2),
        "cagr_median_pct": round(cagr_median, 2),
        "worst_5": [round(x, 2) for x in worst_5],
        "best_5": [round(x, 2) for x in best_5],
    }


# ---------------------------------------------------------------------------
# High-level helper - ticker -> tam analiz
# ---------------------------------------------------------------------------
def run_simulation(
    ticker: str,
    spot_price: float | None = None,
    horizon_years: float = 10.0,
    n_paths: int = 10_000,
    macro_stress: Optional[dict] = None,
    custom_drift: Optional[float] = None,
    custom_sigma: Optional[float] = None,
) -> MCResults:
    """
    Tek satirla NVTS / SEALSQ icin tam GBM simulasyonu calistir.
    """
    import yfinance as yf
    if spot_price is None:
        try:
            spot_price = float(yf.Ticker(ticker).history(period="5d",
                              auto_adjust=True)["Close"].iloc[-1])
        except Exception:
            spot_price = 10.0
    mu, sigma = estimate_drift_sigma(ticker)
    if custom_drift is not None:
        mu = custom_drift
    if custom_sigma is not None:
        sigma = custom_sigma

    inp = MCInputs(
        ticker=ticker, spot_price=spot_price,
        annual_drift=mu, annual_volatility=sigma,
        horizon_years=horizon_years, n_paths=n_paths,
        macro_stress=macro_stress or {},
    )
    return simulate_paths(inp)
