"""
investor_summary.py - Yatirimci icin TEK-BAKIS executive overview.

Karmasik dashboard'un ozeti: her hisse icin 4 sutun:
  1) Hisse & Vizyon  (Orn: "ATOM - Semiconductor IP")
  2) Stratejik Durum (lojistik/teknolojik engel? Critical News tabani)
  3) 10y Confidence Score (Teknik / Temel / Haber ortalamasi)
  4) Verdict (TUT / EKLE / BEKLE / DIKKAT)

Ek olarak:
  - Foundry Capex (TSMC / Intel) korelasyon skoru
  - Apple cap ceiling kontrol
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _foundry_capex_correlation(ticker: str, results: dict,
                                  histories: dict) -> dict:
    """
    Hisse - Foundry Capex (TSM/INTC) korelasyon skoru.

    TSM ve INTC capex artisi tum yari iletken zincirini etkiler. Bu
    korelasyon, hissenin 'sektorel ruzgardan ne kadar etkilendigini' olcer.
    """
    target_df = histories.get(ticker)
    if target_df is None or target_df.empty:
        return {"corr_tsm": None, "corr_intc": None, "avg_capex_corr": None,
                "label": "VERI YOK"}
    target_ret = target_df["Close"].pct_change().dropna()

    out = {"corr_tsm": None, "corr_intc": None}
    for proxy, key in (("TSM", "corr_tsm"), ("INTC", "corr_intc")):
        proxy_df = histories.get(proxy)
        if proxy_df is None or proxy_df.empty:
            continue
        proxy_ret = proxy_df["Close"].pct_change().dropna()
        joined = pd.concat([target_ret, proxy_ret], axis=1).dropna().tail(120)
        if len(joined) >= 30:
            c = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
            out[key] = round(c, 3) if not np.isnan(c) else None

    corrs = [v for v in (out["corr_tsm"], out["corr_intc"]) if v is not None]
    avg = round(float(np.mean(corrs)), 3) if corrs else None
    out["avg_capex_corr"] = avg
    if avg is None:
        out["label"] = "VERI YOK"
    elif avg >= 0.6:
        out["label"] = "GUCLU BAGLI (capex'e cok duyarli)"
    elif avg >= 0.3:
        out["label"] = "ORTA BAGLI"
    elif avg >= 0.1:
        out["label"] = "ZAYIF BAGLI"
    else:
        out["label"] = "BAGIMSIZ (capex'ten etkilenmez)"
    return out


def _strategic_status(r: dict) -> tuple[str, list[str]]:
    """
    Stratejik Durum metni + bayraklar.
    Critical News + Cash Runway + Innovation Risk + Geo Risk birlestir.
    """
    flags = []
    geo = r.get("geo_risk", {}) or {}
    if geo.get("critical_alert"):
        flags.append("🚨 Supply Chain Risk")
    cw = r.get("critical_weight", {}) or {}
    if abs(cw.get("weight", 0)) >= 5:
        sign = "+" if cw["weight"] > 0 else "-"
        flags.append(f"{sign} Critical News")
    moat = r.get("moat", {}) or {}
    if moat.get("innovation_risk"):
        flags.append("⚠️ Innovation Risk (R&D<%15)")
    cr = r.get("cash_runway", {}) or {}
    if cr.get("is_unsustainable"):
        flags.append("💵 Cash <12 ay")
    elif cr.get("is_warning"):
        flags.append("📡 Cash izle")
    so = r.get("strategic_overlay", {}) or {}
    if so.get("overlay_bonus", 0) >= 20:
        flags.append(f"🧬 Stratejik Atilim +{so['overlay_bonus']}")
    elif so.get("overlay_bonus", 0) <= -10:
        flags.append(f"📉 Stratejik Risk {so['overlay_bonus']}")

    # SEALSQ (LAES) icin Q-Day demand spike
    if so.get("details", {}).get("demand_spike_active"):
        flags.append("⚡ Q-Day Demand Spike")
    if so.get("details", {}).get("nist_integration"):
        flags.append("🔐 NIST PQC HW")

    # Competitor Benchmark (AXTI vs IQE/Sumitomo vb.)
    cb = r.get("competitor_benchmark", {}) or {}
    if cb.get("bonus", 0) >= 10:
        flags.append(f"🥊 Rakipten Iyi +{cb['bonus']}")
    elif cb.get("bonus", 0) <= -10:
        flags.append(f"🥊 Rakipten Geride {cb['bonus']}")

    # Moonshot J-Curve sinyali (NVTS, INDI, RGTI + secondary)
    moon = r.get("moonshot", {}) or {}
    if moon.get("master_bonus", 0) >= 20:
        flags.append("🚀 J-Curve Onayli")
    elif moon.get("master_bonus", 0) >= 10:
        flags.append("📈 J-Curve Erken Sinyal")
    elif moon.get("master_bonus", 0) <= -5:
        flags.append("⚠️ Moonshot Yorgun")
    vision = r.get("vision", {}) or {}
    if vision.get("vision_bonus", 0) >= 15:
        flags.append("🎯 Vizyon Ilerleme")
    elif vision.get("vision_bonus", 0) <= -10:
        flags.append("⏰ Vizyon Gecikme")

    if not flags:
        return "Notr - Engel Yok", flags

    # Genel durum: kritik bayrak varsa kirmizi
    has_crit = any("🚨" in f or "Innovation Risk" in f or "<12 ay" in f
                     for f in flags)
    if has_crit:
        status = "ENGEL VAR (riskler aktif)"
    elif any("Atilim" in f or "Ilerleme" in f for f in flags):
        status = "POZITIF KATALIST"
    else:
        status = "Karisik Sinyal"
    return status, flags


def _confidence_10y(r: dict) -> float:
    """
    10y Confidence Score (0..100) = Teknik / Temel / Haber + Durability + Vizyon
    ortalamasi (kullanici talebi).
    """
    master = r.get("master", {}) or {}
    bd = master.get("breakdown", {})
    # Yuzdeye ceviren olcek
    tech_pct = bd.get("technical", 0) / 30 * 100 if "technical" in bd else 0
    fund_pct = bd.get("fundamental", 0) / 20 * 100 if "fundamental" in bd else 0
    news_pct = bd.get("sentiment", 0) / 20 * 100 if "sentiment" in bd else 0
    vision_pct = bd.get("vision", 0) / 30 * 100 if "vision" in bd else 0

    # Durability score 0..100
    durab = r.get("durability_score", {}) or {}
    durab_pct = float(durab.get("durability", durab.get("score", 50)) or 50)

    # Cash runway penaltisi
    cr = r.get("cash_runway", {}) or {}
    runway_pen = abs(cr.get("master_penalty", 0)) * 2  # max -40

    score = (tech_pct * 0.20 + fund_pct * 0.25 + news_pct * 0.15
             + vision_pct * 0.20 + durab_pct * 0.20)
    score -= runway_pen
    return round(max(0, min(100, score)), 1)


def _verdict(confidence: float, master_score: float,
               cash_unsustainable: bool, critical_alert: bool) -> str:
    """
    Verdict cikarimi:
      TUT  -> mevcut pozisyon koru (confidence yuksek + master orta-yuksek)
      EKLE -> pozisyon arttir (confidence + master cok yuksek)
      BEKLE-> kenarda izle (orta)
      DIKKAT/SAT -> azalt veya sat
    """
    if critical_alert or cash_unsustainable:
        return "DIKKAT"
    if confidence >= 70 and master_score >= 75:
        return "EKLE"
    if confidence >= 55 and master_score >= 55:
        return "TUT"
    if confidence >= 40:
        return "BEKLE"
    return "AZALT"


def build_investor_overview(results: dict) -> pd.DataFrame:
    """
    Kullanici talebi: 4-sutun executive table.

    Returns DataFrame:
      Hisse & Vizyon | Stratejik Durum | 10y Confidence | Verdict
    """
    from sector_tam import get_investor_category, STRATEGIC_FOCUS
    from moonshot_detector import get_explosive_factor, MOONSHOT_CANDIDATES
    from engineering_notes import get_critical_threshold

    histories = {t: r.get("df") for t, r in results.items()
                  if r.get("df") is not None}

    rows = []
    for t, r in results.items():
        cat = get_investor_category(t)
        focus = STRATEGIC_FOCUS.get(t, "")
        status, flags = _strategic_status(r)
        conf = _confidence_10y(r)
        master = r.get("master", {}) or {}
        cr = r.get("cash_runway", {}) or {}
        geo = r.get("geo_risk", {}) or {}
        verdict = _verdict(conf, master.get("master_score", 0),
                              cr.get("is_unsustainable", False),
                              geo.get("critical_alert", False))
        cx = _foundry_capex_correlation(t, results, histories)
        ex_factor = get_explosive_factor(t)
        is_moonshot = t.upper() in MOONSHOT_CANDIDATES

        # v8: Kritik Esik (haberden cek) - sabit metin + dinamik tetik durumu
        crit_thresh = get_critical_threshold(t)
        so_details = (r.get("strategic_overlay") or {}).get("details", {})
        crossed = ""
        if t == "NVTS" and so_details.get("tier1_threshold_crossed"):
            crossed = " ✅ TETIKLENDI"
        elif t == "LAES" and so_details.get("nist_integration"):
            crossed = " ✅ TETIKLENDI"
        elif t == "ATOM" and r.get("atom_exponential_mode"):
            crossed = " ✅ TETIKLENDI"

        rows.append({
            "Hisse": t,
            "Stratejik Rol": cat,
            "Odak": focus,
            "Kritik Esik": crit_thresh + crossed,
            "Moonshot": "🚀" if is_moonshot else "",
            "Explosive Factor": ex_factor,
            "Stratejik Durum": status,
            "Bayraklar": ", ".join(flags) if flags else "-",
            "10y Confidence Score": conf,
            "Master Score": master.get("master_score", 0),
            "Verdict": verdict,
            "Foundry Capex Korelasyon": cx.get("avg_capex_corr", "-"),
            "Capex Bagimliligi": cx.get("label", "-"),
        })
    df = pd.DataFrame(rows).sort_values("10y Confidence Score", ascending=False)
    return df


def get_verdict_color(verdict: str) -> str:
    """Verdict renk kodu (UI rozetler icin)."""
    return {
        "EKLE":   "#00c853",
        "TUT":    "#64dd17",
        "BEKLE":  "#ffc107",
        "AZALT":  "#ff6e40",
        "DIKKAT": "#d50000",
    }.get(verdict, "#888")
