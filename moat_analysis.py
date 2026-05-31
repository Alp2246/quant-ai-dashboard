"""
moat_analysis.py - Sirketlerin teknolojik 'moat'unu R&D yogunlugu ile olc.

Eger R&D harcamasi / toplam gelir < %15 ise: 'Inovasyon Riski'
%15-25 arasi: 'Saglikli'
%25+ : 'Lider'
"""
from __future__ import annotations

import logging
from functools import lru_cache

import yfinance as yf

logger = logging.getLogger(__name__)


def _safe(v, default=0.0):
    try:
        if v is None: return default
        f = float(v)
        if f != f: return default
        return f
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=64)
def get_moat(ticker: str) -> dict:
    """
    R&D yogunlugu + brut karlilik + Production Health (HIA cache'inden).

    Returns:
      {
        rd_pct, gross_margin_pct, operating_margin_pct,
        rd_dollars, revenue,
        innovation_risk: bool,
        moat_rating: 'LIDER' | 'SAGLIKLI' | 'ORTA' | 'INOVASYON RISKI',
        message: str,
        moat_score: 0..100,
        production_health: str,
        production_score: 0..100,
        combined_score: agirlikli toplam
      }
    """
    t = yf.Ticker(ticker)
    info = {}
    try:
        info = t.info or {}
    except Exception as e:
        logger.warning("%s moat info: %s", ticker, e)

    revenue = _safe(info.get("totalRevenue"))
    gross_m = _safe(info.get("grossMargins")) * 100
    op_m = _safe(info.get("operatingMargins")) * 100

    # R&D dolari
    rd_dollars = 0.0
    rd_pct = 0.0
    try:
        fin = t.financials
        if fin is not None and not fin.empty:
            for key in ("Research Development", "Research And Development"):
                if key in fin.index:
                    rd_dollars = _safe(fin.loc[key].iloc[0])
                    break
    except Exception as e:
        logger.debug("%s R&D fetch: %s", ticker, e)

    if revenue > 0 and rd_dollars > 0:
        rd_pct = rd_dollars / revenue * 100

    # Rating
    if rd_pct >= 25:
        rating = "LIDER"
        message = f"R&D %{rd_pct:.1f} - sektor lideri tekno yatirim"
        risk = False
        score = 90
    elif rd_pct >= 15:
        rating = "SAGLIKLI"
        message = f"R&D %{rd_pct:.1f} - saglikli inovasyon harcamasi"
        risk = False
        score = 70
    elif rd_pct >= 8:
        rating = "ORTA"
        message = f"R&D %{rd_pct:.1f} - sektor ortalamasi alti, izle"
        risk = False
        score = 50
    elif rd_pct > 0:
        rating = "INOVASYON RISKI"
        message = (f"⚠️ R&D %{rd_pct:.1f} - %15 esiginin altinda. "
                   f"10y vadede teknolojik geride kalma riski.")
        risk = True
        score = 25
    else:
        rating = "VERI YOK"
        message = "R&D verisi cekilemedi (privately held / yetersiz disclosure)"
        risk = False
        score = 0

    # Gross margin desteklemesi - >%50 = saglam moat (fiyatlama gucu)
    pricing_power = "ZAYIF"
    if gross_m >= 60:
        pricing_power = "COK GUCLU"
    elif gross_m >= 40:
        pricing_power = "GUCLU"
    elif gross_m >= 25:
        pricing_power = "ORTA"
    elif gross_m > 0:
        pricing_power = "ZAYIF"

    # Production Health (HIA cache'inden, lazy import)
    prod_health = "❓ HIA henuz taranmadi"
    prod_score = 0
    avg_yield = None
    try:
        from hardware_intel import get_production_score
        ps = get_production_score(ticker)
        prod_health = ps.get("production_health", prod_health)
        prod_score = int(ps.get("production_score", 0) or 0)
        avg_yield = ps.get("avg_yield_pct")
    except Exception as e:
        logger.debug("production score (%s): %s", ticker, e)

    # Combined moat: R&D moat (60%) + production health (40%)
    if prod_score > 0:
        combined = round(score * 0.60 + prod_score * 0.40, 1)
    else:
        combined = score

    return {
        "ticker": ticker,
        "rd_pct": round(rd_pct, 2),
        "rd_dollars_m": round(rd_dollars / 1e6, 1),
        "gross_margin_pct": round(gross_m, 1),
        "operating_margin_pct": round(op_m, 1),
        "revenue_m": round(revenue / 1e6, 1),
        "innovation_risk": risk,
        "moat_rating": rating,
        "moat_score": score,
        "pricing_power": pricing_power,
        "message": message,
        "production_health": prod_health,
        "production_score": prod_score,
        "avg_yield_pct": avg_yield,
        "combined_moat_score": combined,
    }
