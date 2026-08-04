"""
black_litterman.py - Black-Litterman portfolio optimization.

Klasik Mean-Variance Optimization (Markowitz) problemli:
  - Tarihsel ortalama getiriler cok dalgali -> portfoy agirliklari ekstrem.
  - Yatirimcinin kendi gorusunu modele dahil etmek imkansiz.

Black-Litterman 1990'larda Goldman Sachs'ta gelistirildi. Mantik:
  1) Piyasa dengesinde 'implied' getiri = tau * Sigma * w_market
  2) Yatirimci 'absolute view' veya 'relative view' belirler:
       "ATOM yillik %35 getiri vermeli" (absolute)
       "IONQ-RGTI'den %10 daha iyi olmali" (relative)
  3) Bu gorusler matematiksel olarak posterior return'e blend edilir
  4) Posterior return + Sigma -> optimum portfoy agirligi

Kullanim:
  from black_litterman import portfolio_optimization
  result = portfolio_optimization(returns_df, market_caps,
                                    views=[{"ticker": "ATOM",
                                             "expected_annual_return": 0.35,
                                             "confidence": 0.7}])
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _safe_inv(M: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    """Ridge regularization ile guvenli matris inversi."""
    n = M.shape[0]
    return np.linalg.inv(M + ridge * np.eye(n))


def implied_returns(market_caps: dict, cov_matrix: pd.DataFrame,
                      risk_aversion: float = 2.5) -> pd.Series:
    """
    Piyasa dengesi implied annual returns (reverse optimization).

    Pi = lambda * Sigma * w_market

    lambda = risk_aversion (default 2.5 = piyasa Sharpe ~0.5 / vol 0.2)
    """
    tickers = list(cov_matrix.columns)
    caps = np.array([market_caps.get(t, 1.0) for t in tickers], dtype=float)
    caps = caps / caps.sum()
    Sigma = cov_matrix.values
    Pi = risk_aversion * Sigma.dot(caps)
    return pd.Series(Pi, index=tickers)


def black_litterman_posterior(
    pi: pd.Series,
    cov_matrix: pd.DataFrame,
    views: list[dict],
    tau: float = 0.05,
) -> dict:
    """
    Black-Litterman posterior return.

    views: [{"ticker": "ATOM", "expected_annual_return": 0.35,
              "confidence": 0.7},  # 0..1, 1=tam emin
             {"ticker": ["IONQ","RGTI"], "weights":[1,-1],
              "expected_annual_return": 0.10,  # relative IONQ-RGTI = +10%
              "confidence": 0.5},  ...]

    Returns dict with posterior returns, weights, P, Q, Omega matrices.
    """
    tickers = list(cov_matrix.columns)
    n = len(tickers)
    Sigma = cov_matrix.values
    Pi = pi.values.reshape(-1, 1)

    if not views:
        return {"posterior_returns": pi.copy(),
                "pi_prior": pi.copy(),
                "weights": pd.Series([1/n]*n, index=tickers)}

    k = len(views)
    P = np.zeros((k, n))
    Q = np.zeros((k, 1))
    Omega = np.zeros((k, k))

    for i, v in enumerate(views):
        Q[i, 0] = float(v["expected_annual_return"])
        conf = float(v.get("confidence", 0.5))
        # conf -> Omega: dusuk conf = yuksek belirsizlik (Omega buyuk)
        # Idzorek 2005: omega_i = (1/conf - 1) * tau * P_i * Sigma * P_i'
        if isinstance(v["ticker"], str):
            if v["ticker"] not in tickers:
                continue
            idx = tickers.index(v["ticker"])
            P[i, idx] = 1.0
        else:
            # Relative view: ["A","B"] + weights[1,-1]
            for tt, w in zip(v["ticker"], v.get("weights", [1, -1])):
                if tt in tickers:
                    P[i, tickers.index(tt)] = float(w)
        # Omega_ii
        p_row = P[i, :].reshape(1, -1)
        var_view = float(np.atleast_2d(p_row.dot(Sigma).dot(p_row.T))[0, 0])
        # conf=1 -> Omega cok kucuk; conf->0 -> Omega cok buyuk
        omega_i = max(1e-8, (1.0/max(conf, 0.01) - 1.0) * tau * var_view)
        Omega[i, i] = omega_i

    tauSigma = tau * Sigma
    inv_tauSigma = _safe_inv(tauSigma)
    inv_Omega = _safe_inv(Omega) if k > 0 else np.zeros((0, 0))

    # Posterior return (Black-Litterman master formula)
    A = inv_tauSigma + P.T.dot(inv_Omega).dot(P)
    B = inv_tauSigma.dot(Pi) + P.T.dot(inv_Omega).dot(Q)
    post_returns = _safe_inv(A).dot(B).flatten()
    post_returns = pd.Series(post_returns, index=tickers)

    # Optimum portfoy agirlik (lambda=2.5)
    lam = 2.5
    inv_Sigma = _safe_inv(Sigma)
    raw_w = (1/lam) * inv_Sigma.dot(post_returns.values)
    raw_w = np.clip(raw_w, 0, 1)
    if raw_w.sum() == 0:
        weights = pd.Series([1/n]*n, index=tickers)
    else:
        weights = pd.Series(raw_w / raw_w.sum(), index=tickers)

    return {
        "pi_prior": pi.copy(),
        "posterior_returns": post_returns,
        "weights": weights,
        "P": pd.DataFrame(P, columns=tickers),
        "Q": Q.flatten(),
        "Omega_diag": np.diag(Omega),
    }


def portfolio_optimization(
    histories: dict[str, pd.DataFrame],
    market_caps: dict[str, float] | None = None,
    views: list[dict] | None = None,
    risk_aversion: float = 2.5,
    tau: float = 0.05,
) -> dict:
    """
    End-to-end portfoy optim:
      1) Histories -> log return -> annual cov matrix
      2) Market caps -> implied returns (Pi)
      3) Investor views (varsa) -> Black-Litterman posterior
      4) Long-only optimum weights

    Returns:
      {
        weights: Series,
        prior_returns: Series (annual %),
        posterior_returns: Series (annual %),
        cov_annual: DataFrame,
        expected_portfolio_return: float (annual %),
        expected_portfolio_vol: float (annual %),
        sharpe_ratio: float,
      }
    """
    closes = {}
    for t, df in histories.items():
        if df is None or df.empty or "Close" not in df.columns:
            continue
        c = df["Close"].dropna()
        if len(c) < 60:
            continue
        closes[t] = c
    if len(closes) < 2:
        return {"error": "Yetersiz hisse - en az 2 hisse gerekli"}

    aligned = pd.DataFrame(closes).dropna()
    if len(aligned) < 60:
        return {"error": "Yetersiz overlap (60 gun minimum gerekli)"}

    log_ret = np.log(aligned / aligned.shift(1)).dropna()
    annual_cov = log_ret.cov() * 252
    annual_mean = log_ret.mean() * 252

    # Market caps default = esit agirlik.
    # DIKKAT: bu durumda Pi "piyasa dengesi implied getirisi" DEGILDIR —
    # esit agirlikli uydurma bir prior'dur ve posterior yorumlanamaz.
    # Cagiran taraf bunu bilsin diye kaynagi raporluyoruz.
    caps_source = "marketcap"
    if not market_caps:
        market_caps = {t: 1.0 for t in aligned.columns}
        caps_source = "equal_weight_fallback"
    else:
        usable = [t for t in aligned.columns
                  if isinstance(market_caps.get(t), (int, float))
                  and market_caps.get(t)]
        if len(usable) < len(aligned.columns):
            caps_source = ("equal_weight_fallback" if not usable
                           else "partial_marketcap")

    pi = implied_returns(market_caps, annual_cov, risk_aversion=risk_aversion)

    bl = black_litterman_posterior(pi, annual_cov, views or [], tau=tau)
    w = bl["weights"]
    post = bl["posterior_returns"]

    # Beklenen portfoy getiri / vol
    exp_ret = float(w.values.dot(post.values))
    exp_var = float(w.values.dot(annual_cov.values).dot(w.values))
    exp_vol = float(np.sqrt(max(0.0, exp_var)))
    sharpe = exp_ret / exp_vol if exp_vol > 0 else 0.0

    return {
        "weights": w,
        "prior_returns_pct": (pi * 100).round(2),
        "posterior_returns_pct": (post * 100).round(2),
        "historical_returns_pct": (annual_mean * 100).round(2),
        "cov_annual": annual_cov,
        "expected_portfolio_return_pct": round(exp_ret * 100, 2),
        "expected_portfolio_vol_pct": round(exp_vol * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "views_applied": views or [],
        "n_tickers": len(aligned.columns),
        "n_observations": len(log_ret),
        # Prior'un kaynagi: "marketcap" ise Pi gercekten piyasa dengesi;
        # "equal_weight_fallback" ise POSTERIOR YORUMLANAMAZ.
        "source": caps_source,
    }
