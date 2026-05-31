"""
cash_runway.py - Spekulatif hisseler icin 'Cash Runway' hesabi.

Formul (basit):
  Cash Runway (months) = (Cash + Short-term Investments) / |Quarterly Burn| * 3

yfinance:
  - info["totalCash"]                       -> nakit + esdegerler
  - cashflow.loc["Free Cash Flow"]           -> quarterly free cash flow
  - quarterly_cashflow.loc[...]              -> aksi durumda son ceyrek

Eger Cash Runway < 12 ay ise 'Finansal Surdurulebilirlik Riski' uyarisi
verilir. Bu uyari ozellikle spekulatif hisseler (IONQ, RGTI, ATOM, LAES,
QUBT) icin master score'a -15 ceza olarak yansir.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import yfinance as yf

logger = logging.getLogger(__name__)


def _safe(v, default=0.0):
    try:
        if v is None:
            return default
        f = float(v)
        if f != f:  # NaN
            return default
        return f
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=64)
def compute_cash_runway(ticker: str) -> dict:
    """
    Hisse icin Cash Runway hesabi.

    Returns:
      {
        ticker, cash_usd_m, quarterly_burn_usd_m, runway_months,
        runway_quarters, is_unsustainable: bool (<12 ay),
        is_warning: bool (<24 ay), is_critical: bool (<6 ay),
        label, master_penalty (-15..0),
        free_cash_flow_yearly, raw: {...}
      }
    """
    info = {}
    cf = None
    qcf = None
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        try: cf = t.cashflow
        except Exception: pass
        try: qcf = t.quarterly_cashflow
        except Exception: pass
    except Exception as e:
        logger.warning("cash_runway %s info: %s", ticker, e)

    cash = _safe(info.get("totalCash"))
    if cash == 0:
        cash = _safe(info.get("cash"))
    fcf_year = _safe(info.get("freeCashflow"))

    # Yearly FCF -> quarterly burn (negatif FCF burn anlamina gelir)
    quarterly_burn = 0.0
    burn_source = ""
    # 1. Tercih: yearly FCF / 4 (eger negatifse burn rate)
    if fcf_year < 0:
        quarterly_burn = abs(fcf_year) / 4
        burn_source = "yearly_fcf"
    elif qcf is not None and not qcf.empty:
        # 2. Tercih: quarterly cashflow tablosundan en son negatif FCF
        for key in ("Free Cash Flow", "Operating Cash Flow", "Cash Flow From Operations"):
            if key in qcf.index:
                vals = qcf.loc[key].dropna()
                if len(vals):
                    last_q = _safe(vals.iloc[0])
                    if last_q < 0:
                        quarterly_burn = abs(last_q)
                        burn_source = f"qcf_{key}"
                        break

    # 3. Tercih: cashflow yearly tablosu
    if quarterly_burn == 0 and cf is not None and not cf.empty:
        for key in ("Free Cash Flow", "Operating Cash Flow"):
            if key in cf.index:
                vals = cf.loc[key].dropna()
                if len(vals):
                    last_y = _safe(vals.iloc[0])
                    if last_y < 0:
                        quarterly_burn = abs(last_y) / 4
                        burn_source = f"yearly_{key}"
                        break

    runway_months = None
    if quarterly_burn > 0 and cash > 0:
        runway_months = round(cash / quarterly_burn * 3, 1)
    elif cash > 0 and quarterly_burn == 0:
        runway_months = 999  # kar ediyor / burn yok
    elif cash == 0 and quarterly_burn > 0:
        runway_months = 0
    else:
        runway_months = None  # belirsiz

    # Sınıflandırma
    is_critical = False
    is_unsustainable = False
    is_warning = False
    penalty = 0
    if runway_months is None:
        label = "❓ VERI YOK"
    elif runway_months >= 999 or quarterly_burn <= 0:
        label = "🟢 KARLI / BURN YOK"
    elif runway_months < 6:
        is_critical = True
        is_unsustainable = True
        is_warning = True
        penalty = -20
        label = "🚨 KRITIK (<6 ay)"
    elif runway_months < 12:
        is_unsustainable = True
        is_warning = True
        penalty = -15
        label = "⚠️ SURDURULEMEZ (<12 ay)"
    elif runway_months < 24:
        is_warning = True
        penalty = -5
        label = "📡 IZLE (12-24 ay)"
    elif runway_months < 48:
        penalty = 0
        label = "✅ ORTA (24-48 ay)"
    else:
        penalty = 0
        label = "💎 GUVENLI (>48 ay)"

    return {
        "ticker": ticker,
        "cash_usd_m": round(cash / 1e6, 1) if cash else 0,
        "quarterly_burn_usd_m": round(quarterly_burn / 1e6, 1)
                                  if quarterly_burn else 0,
        "yearly_burn_usd_m": round(quarterly_burn * 4 / 1e6, 1)
                                  if quarterly_burn else 0,
        "runway_months": runway_months,
        "runway_quarters": (round(runway_months / 3, 1)
                            if runway_months and runway_months < 999
                            else None),
        "is_critical": is_critical,
        "is_unsustainable": is_unsustainable,
        "is_warning": is_warning,
        "master_penalty": penalty,
        "label": label,
        "burn_source": burn_source,
        "free_cash_flow_yearly_m": round(fcf_year / 1e6, 1) if fcf_year else 0,
    }
