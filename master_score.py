"""
master_score.py — Hibrit Guven Endeksi (Master Score v9)

Akademik Referans:
  - Fama, E. F., & French, K. R. (1993). *Common risk factors in returns on
    stocks and bonds*. (Cok-faktorlu skor yapisi.)
  - Lopez de Prado, M. (2018). *Advances in Financial ML*, Ch.3 (meta-labeling)
    - 'research_coef' (kappa) buradan tureyen MDA dinamik carpani.
  - Wilson, E. B. (1927). Binomial guven araligi - prob_up icin.

Formul (Math_Specs.md Bolum 1):
  Master_Score = clip[0,100]( B * kappa + M )
  B     = T + V + F + S        (taban: 30+30+20+20)
  M     = sum(modifier'lar)    (sektor, capex, makro, stratejik, jeo, ...)
  kappa = research_coef in [0.5, 1.5]
"""
from __future__ import annotations

import numpy as np


def compute_master_score(
    technical: dict,
    sentiment: dict,
    fundamental: dict,
    ml_result: dict,
    vision: dict | None = None,
    critical_weight: dict | None = None,
    sector_weight: dict | None = None,
    capex_weight: dict | None = None,
    fear_level: float = 0,
    moat: dict | None = None,
    patent_bonus: int = 0,
    geo_risk: dict | None = None,
    cycle_modifier: int = 0,
    macro_bonus: int = 0,
    research_coef: float = 1.0,
    research_intensity: float = 0.0,
    strategic_overlay_bonus: int = 0,
    runway_penalty: int = 0,
    moonshot_bonus: int = 0,
) -> dict:
    """
    Master Score 0..100 - YENI AGIRLIK 30/30/20/20:

      Teknik (Zamanlama)              30 puan
      Vizyon/Roadmap (Strateji)       30 puan   <- vision_bonus -15..+20 -> 0..30
      Temel/Finansal (Guvenlik)       20 puan
      Sektorel Haber/Duyarlilik       20 puan   (haber 10 + reddit 10)

    Modifier'lar (Master Score'a son ekleme):
      Sector Chain      ±5  (NVDA->ASML, EV->WOLF zincirleri)
      Capex Watch       ±5  (TSMC/Samsung/Intel capex haberleri)
      Critical News     ±10 (ASML/SMIC EUV ihracat haberleri)
      Volatility Fear    -5..0 (yuksek IV korkusu)
      Moat / Innovation -10..0 (R&D < %15 -> ceza)
      Strategic Overlay  -40..+40 (IONQ/RGTI/ATOM/LAES domain)
      Cash Runway        -20..0   (speculative, <12 ay nakit)
      Moonshot J-Curve   -5..+20  (NVTS/INDI/RGTI sicrama adaylari)

    Master clip[0, 100].
    """
    # ---- Teknik (30 puan) -------------------------------------------
    rsi = technical.get("rsi", 50)
    macd_sig = technical.get("macd_signal", "neutral")
    close = technical.get("close", 0)
    sma20 = technical.get("sma_20", close)
    sma50 = technical.get("sma_50", close)

    rsi_pt = 0
    if 35 <= rsi <= 65:
        rsi_pt = 9
    elif 30 <= rsi < 35 or 65 < rsi <= 70:
        rsi_pt = 6
    elif rsi < 30 or rsi > 75:
        rsi_pt = 2

    macd_pt = 9 if macd_sig == "bullish" else (3 if macd_sig == "neutral" else 0)

    sma_pt = 0
    if close > sma20:
        sma_pt += 3
    if close > sma50:
        sma_pt += 3

    prob_up = ml_result.get("prob_up", 0.5)
    ml_pt = max(0, min(6, (prob_up - 0.35) / 0.30 * 6))

    technical_total = round(rsi_pt + macd_pt + sma_pt + ml_pt, 1)

    # ---- Vizyon/Roadmap (30 puan) -----------------------------------
    # vision_bonus -15..+20 -> doğrusal scale 0..30 (notr=10)
    vision_bonus = 0
    vision_rating = "VIZYON YOK"
    if vision:
        vision_bonus = vision.get("vision_bonus", 0)
        vision_rating = vision.get("rating", "VIZYON YOK")
    vision_total = max(0, min(30, 10 + vision_bonus * 0.85))
    vision_total = round(vision_total, 1)

    # ---- Sektorel Haber/Duyarlilik (20 puan) ------------------------
    news_s = sentiment.get("news_score", sentiment.get("score", 0))
    reddit_s = sentiment.get("reddit_score", 0)
    news_pt = max(0, min(10, (news_s + 0.3) / 0.6 * 10))
    reddit_pt = max(0, min(10, (reddit_s + 0.3) / 0.6 * 10))
    sentiment_total = round(news_pt + reddit_pt, 1)

    # ---- Temel (20 puan) --------------------------------------------
    fund_score = fundamental.get("score", 50)
    fundamental_total = round(fund_score / 100 * 20, 1)

    # ---- Taban Master ------------------------------------------------
    base = round(technical_total + vision_total + fundamental_total +
                  sentiment_total, 1)

    # ---- Modifier'lar -------------------------------------------------
    crit_w = critical_weight.get("weight", 0) if critical_weight else 0
    sec_w = sector_weight.get("sector_weight", 0) if sector_weight else 0
    cap_w = capex_weight.get("capex_weight", 0) if capex_weight else 0

    # Korku endeksi cezasi: fear_level > 50 ise master'dan -5
    fear_penalty = 0
    if fear_level >= 70:
        fear_penalty = -5
    elif fear_level >= 50:
        fear_penalty = -3

    # Moat/Innovation cezasi
    moat_penalty = 0
    if moat and moat.get("innovation_risk"):
        moat_penalty = -5

    # HIA: Patent bonusu (0..+5) -> vision dimension'ina ek
    patent_b = max(0, min(5, int(patent_bonus or 0)))

    # HIA: Jeopolitik supply-chain riski -> export_weight (-15..+10)
    # Kritik export filter (Ga/Ge/InP/EUV) -> -15 hard penalty
    geo_w = 0
    if geo_risk:
        geo_raw = int(geo_risk.get("export_weight", 0) or 0)
        # Yeni alt sinir -15 (CRITICAL EXPORT BLOCK), ust sinir +10 ayni
        geo_w = max(-15, min(10, geo_raw))

    # HIA: Semi cycle phase modifier (-3..+3)
    cycle_m = max(-3, min(3, int(cycle_modifier or 0)))

    # MAKRO BONUS: Expansion fazinda +10, Downturn -10 (V7 kullanici talebi)
    macro_b = max(-10, min(10, int(macro_bonus or 0)))

    # RESEARCH AGENT: Lopez de Prado MDA tarzi dinamik carpan (0.5..1.5)
    # Net bullish + yuksek intensity -> taban skoru carparak yukseltir.
    # Bu sadece TABAN skoru carpar, modifier'lara dokunmaz.
    coef = max(0.5, min(1.5, float(research_coef or 1.0)))
    base_scaled = base * coef

    # Stratejik Beklenti (kuantum sepeti, ATOM lisans, SEALSQ PQC vs.)
    # ±30 master clamp (master score'un saturation'a yapismasini onler;
    # overlay'in kendi ham bonusu raporlamada full gosterilir).
    strat_b = max(-30, min(30, int(strategic_overlay_bonus or 0)))

    # Finansal surdurulebilirlik (cash runway < 12 ay)
    runway_p = max(-20, min(0, int(runway_penalty or 0)))

    # Moonshot J-Curve bonusu (NVTS, INDI, RGTI + secondary)
    moon_b = max(-5, min(20, int(moonshot_bonus or 0)))

    total_modifier = (crit_w + sec_w + cap_w + fear_penalty + moat_penalty +
                       patent_b + geo_w + cycle_m + macro_b + strat_b +
                       runway_p + moon_b)

    master = max(0, min(100, round(base_scaled + total_modifier, 1)))

    from verdict_rules import verdict_for
    rating = verdict_for(master)

    ci = _confidence_interval(prob_up, ml_result.get("train_samples", 100))

    return {
        "master_score": master,
        "base_score": base,
        "vision_bonus": vision_bonus,
        "vision_rating": vision_rating,
        "critical_weight": crit_w,
        "sector_weight": sec_w,
        "capex_weight": cap_w,
        "fear_penalty": fear_penalty,
        "moat_penalty": moat_penalty,
        "rating": rating,
        "breakdown": {
            "technical":   technical_total,    # 30 max
            "vision":      vision_total,       # 30 max
            "fundamental": fundamental_total,  # 20 max
            "sentiment":   sentiment_total,    # 20 max (news+reddit)
            "news":        round(news_pt, 1),  # 10 max
            "reddit":      round(reddit_pt, 1), # 10 max
        },
        "modifiers": {
            "sector":   sec_w,
            "capex":    cap_w,
            "critical": crit_w,
            "fear":     fear_penalty,
            "moat":     moat_penalty,
            "patent":   patent_b,    # HIA: stratejik patent bonusu
            "geo":      geo_w,        # HIA: ihracat / supply-chain
            "cycle":    cycle_m,      # HIA: semi cycle phase
            "macro":    macro_b,      # V7: Expansion +10 Makro Bonus
            "strategic": strat_b,     # IONQ/RGTI/ATOM/LAES overlay
            "runway":   runway_p,     # Cash runway < 12 ay
            "moonshot": moon_b,       # J-Curve sicrama bonusu
        },
        "strategic_overlay_bonus": strat_b,
        "runway_penalty": runway_p,
        "research_coef": coef,        # V7: Lopez de Prado MDA dynamic coef
        "research_intensity": round(float(research_intensity or 0.0), 1),
        "base_scaled": round(base_scaled, 1),
        "components": {
            "rsi_pt": round(rsi_pt, 1),
            "macd_pt": round(macd_pt, 1),
            "sma_pt": round(sma_pt, 1),
            "ml_pt": round(ml_pt, 1),
            "news_pt": round(news_pt, 1),
            "reddit_pt": round(reddit_pt, 1),
            "fundamental_pt": round(fundamental_total, 1),
        },
        "confidence_low": ci[0],
        "confidence_high": ci[1],
        "ml_prob_up": prob_up,
    }


def _confidence_interval(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson skor araligi - binomial proba icin guven araligi."""
    n = max(n, 20)
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = (z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    lo = max(0.0, centre - margin)
    hi = min(1.0, centre + margin)
    return round(lo, 3), round(hi, 3)
