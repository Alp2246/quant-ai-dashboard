"""
executive_brief.py - Her hisse icin DOGAL DIL yorum + aksiyon onerisi.

Rule-based (LLM-siz). Master Score'un modifier'larini, vizyon/overlay
sinyallerini ve cash runway'i okuyup yatirimci-dostu Turkce metin uretir.

Cikti:
  - Hisse basina 3-5 cumlelik 'brief'
  - Genel piyasa ozeti (kac EKLE / TUT / DIKKAT, hangi sektor guclu)
"""
from __future__ import annotations

from typing import Dict, List, Any


# Aksiyonlar
ACTION_TEXT = {
    "EKLE":   "📈 Pozisyon arttirilabilir.",
    "TUT":    "✅ Mevcut pozisyonu koru.",
    "BEKLE":  "⏸️ Kenarda izle - net katalist bekle.",
    "AZALT":  "⚠️ Pozisyon kucult.",
    "DIKKAT": "🚨 Cikis dusun - kritik risk aktif.",
}


def _master_components_story(r: dict) -> List[str]:
    """Master Score breakdown -> hangi boyut baskin?"""
    bd = (r.get("master", {}) or {}).get("breakdown", {})
    stories = []
    techp = bd.get("technical", 0)
    if techp >= 22:
        stories.append(f"teknik momentum guclu ({techp:.0f}/30)")
    elif techp <= 12:
        stories.append(f"teknik zayif ({techp:.0f}/30)")

    visionp = bd.get("vision", 0)
    if visionp >= 22:
        stories.append(f"vizyon/roadmap yuksek ({visionp:.0f}/30)")
    elif visionp <= 10:
        stories.append(f"vizyon zayif ({visionp:.0f}/30)")

    fundp = bd.get("fundamental", 0)
    if fundp >= 15:
        stories.append(f"temel saglam ({fundp:.0f}/20)")
    elif fundp <= 8:
        stories.append(f"temel zayif ({fundp:.0f}/20)")

    sentp = bd.get("sentiment", 0)
    if sentp >= 14:
        stories.append(f"haber pozitif ({sentp:.0f}/20)")
    elif sentp <= 6:
        stories.append(f"haber negatif ({sentp:.0f}/20)")
    return stories


def _modifiers_story(r: dict) -> List[str]:
    """Master modifier'lardan dikkat cekenleri ozetler."""
    mods = (r.get("master", {}) or {}).get("modifiers", {})
    out = []
    if mods.get("strategic", 0) >= 15:
        out.append(f"stratejik overlay +{mods['strategic']} (domain katalist)")
    elif mods.get("strategic", 0) <= -10:
        out.append(f"stratejik overlay {mods['strategic']} (domain risk)")
    if mods.get("moonshot", 0) >= 12:
        out.append(f"J-Curve +{mods['moonshot']} (gelir/R&D paralel buyume)")
    elif mods.get("moonshot", 0) <= -3:
        out.append(f"moonshot yorgun {mods['moonshot']}")
    if mods.get("critical", 0) >= 5:
        out.append(f"kritik haber +{mods['critical']}")
    elif mods.get("critical", 0) <= -5:
        out.append(f"kritik haber {mods['critical']}")
    if mods.get("macro", 0) >= 5:
        out.append(f"makro ruzgar +{mods['macro']}")
    elif mods.get("macro", 0) <= -5:
        out.append(f"makro daralma {mods['macro']}")
    if mods.get("runway", 0) <= -5:
        out.append(f"cash runway cezasi {mods['runway']}")
    if mods.get("moat", 0) <= -3:
        out.append(f"moat zayif {mods['moat']}")
    return out


def _risk_story(r: dict) -> List[str]:
    """Cash runway + geo + speculative risk."""
    out = []
    cr = r.get("cash_runway", {}) or {}
    if cr.get("is_unsustainable"):
        rm = cr.get("runway_months")
        out.append(f"⛔ Cash runway {rm:.0f} ay - finansal surdurulebilirlik riski")
    elif cr.get("is_warning"):
        rm = cr.get("runway_months")
        out.append(f"📡 Cash runway {rm:.0f} ay - izleme modunda")
    geo = r.get("geo_risk", {}) or {}
    if geo.get("critical_alert"):
        out.append("🚨 Tedarik zinciri / ihracat riski (kirmizi alarm)")
    moat = r.get("moat", {}) or {}
    if moat.get("innovation_risk"):
        out.append(f"⚠️ Inovasyon riski (R&D oran %{moat.get('rd_pct', 0):.0f} < 15)")
    return out


def _opportunity_story(r: dict) -> List[str]:
    """Pozitif katalistler."""
    out = []
    so = r.get("strategic_overlay", {}) or {}
    if so.get("labels"):
        # Top 2 etiketi al
        for lbl in so["labels"][:2]:
            out.append(lbl)
    cb = r.get("competitor_benchmark", {}) or {}
    if cb.get("bonus", 0) >= 10:
        out.append(f"🥊 Rakipten guclu: {cb.get('label', '')} "
                     f"({cb.get('relative_strength_pp', 0):+.0f}pp)")
    elif cb.get("bonus", 0) <= -10:
        out.append(f"🥊 Rakipten zayif: {cb.get('label', '')}")
    m = r.get("moonshot", {}) or {}
    if m.get("is_moonshot_candidate") and m.get("master_bonus", 0) > 0:
        rev = m.get("revenue_yoy_pct")
        rd = m.get("rd_yoy_pct")
        if rev is not None and rd is not None:
            out.append(f"🚀 Moonshot J-Curve: Revenue YoY %{rev:+.0f}, "
                         f"R&D YoY %{rd:+.0f}")
    return out


def _action_line(r: dict, verdict: str) -> str:
    """Aksiyon cumlesi - hisseye ozel."""
    t = r.get("ticker", "")
    ms = (r.get("master", {}) or {}).get("master_score", 0)
    base = ACTION_TEXT.get(verdict, "")

    # Tickere-ozel ek notlar
    if t == "NVTS":
        cr = r.get("cash_runway", {}) or {}
        oem = (r.get("strategic_overlay", {})
                  .get("details", {}).get("tier1_threshold_crossed"))
        if oem:
            base += " Tier-1 OEM esigi tetiklendi - **AGRESIF EKLE**."
        else:
            base += " Tier-1 OEM (Tesla/VW/Hyundai) anlasmasi takip et."
    elif t == "LAES":
        nist = (r.get("strategic_overlay", {})
                  .get("details", {}).get("nist_integration"))
        if nist:
            base += " NIST PQC HW entegrasyonu onayli - Q-Day katalisti yakin."
    elif t == "ATOM":
        exp = r.get("atom_exponential_mode")
        if exp:
            base += " Foundry MST kabulu - EXPONENTIAL mod aktif."
        else:
            base += " JDA / Foundry lisans haberini bekle."
    elif t in ("IONQ", "RGTI"):
        base += " Kuantum sepet (IONQ-RGTI birlikte degerlendir)."
    elif t == "AXTI":
        cb = r.get("competitor_benchmark", {}) or {}
        if cb.get("bonus", 0) >= 5:
            base += " IQE/Sumitomo'dan pay aliyor."
    return base


def brief_for_ticker(r: dict) -> dict:
    """
    Bir hisse icin executive brief.

    Returns:
      {
        ticker, master_score, verdict, summary, opportunities[],
        risks[], action
      }
    """
    t = r.get("ticker", "")
    master = r.get("master", {}) or {}
    ms = master.get("master_score", 0)
    rating = master.get("rating", "")

    # Verdict (investor_summary mantigi tekrari)
    cr = r.get("cash_runway", {}) or {}
    geo = r.get("geo_risk", {}) or {}
    # Confidence proxy: 10y confidence approx
    bd = master.get("breakdown", {})
    tech_pct = bd.get("technical", 0) / 30 * 100 if "technical" in bd else 0
    fund_pct = bd.get("fundamental", 0) / 20 * 100 if "fundamental" in bd else 0
    news_pct = bd.get("sentiment", 0) / 20 * 100 if "sentiment" in bd else 0
    vision_pct = bd.get("vision", 0) / 30 * 100 if "vision" in bd else 0
    durab = r.get("durability_score", {}) or {}
    durab_pct = float(durab.get("durability", durab.get("score", 50)) or 50)
    conf = (tech_pct*0.20 + fund_pct*0.25 + news_pct*0.15
            + vision_pct*0.20 + durab_pct*0.20)
    conf -= abs(cr.get("master_penalty", 0)) * 2

    if cr.get("is_unsustainable") or geo.get("critical_alert"):
        verdict = "DIKKAT"
    elif conf >= 70 and ms >= 75:
        verdict = "EKLE"
    elif conf >= 55 and ms >= 55:
        verdict = "TUT"
    elif conf >= 40:
        verdict = "BEKLE"
    else:
        verdict = "AZALT"

    # Hikaye parcalari
    comp_st = _master_components_story(r)
    mod_st = _modifiers_story(r)
    opp = _opportunity_story(r)
    risks = _risk_story(r)

    # Cumle birlestirme
    intro = f"**{t}** — Master Score **{ms:.1f}** ({rating}). "
    if comp_st:
        intro += "Profil: " + ", ".join(comp_st) + ". "
    if mod_st:
        intro += "Etkiler: " + ", ".join(mod_st) + "."

    action = _action_line(r, verdict)

    return {
        "ticker": t,
        "master_score": ms,
        "verdict": verdict,
        "rating": rating,
        "confidence_10y": round(conf, 1),
        "summary": intro,
        "opportunities": opp,
        "risks": risks,
        "action": action,
    }


def market_summary(briefs: List[dict]) -> dict:
    """Tum hisseler uzerinden piyasa ozetini cikar."""
    counts = {}
    for b in briefs:
        v = b.get("verdict", "BEKLE")
        counts[v] = counts.get(v, 0) + 1
    avg_master = round(
        sum(b.get("master_score", 0) for b in briefs) / max(1, len(briefs)), 1)
    avg_conf = round(
        sum(b.get("confidence_10y", 0) for b in briefs) / max(1, len(briefs)),
        1)

    # En guclu / en zayif
    if briefs:
        strongest = max(briefs, key=lambda b: b.get("master_score", 0))
        weakest = min(briefs, key=lambda b: b.get("master_score", 0))
    else:
        strongest = weakest = None

    # Piyasa cumlesi
    n_ekle = counts.get("EKLE", 0)
    n_tut = counts.get("TUT", 0)
    n_bekle = counts.get("BEKLE", 0)
    n_dikkat = counts.get("DIKKAT", 0) + counts.get("AZALT", 0)
    n = max(1, len(briefs))
    pos_pct = (n_ekle + n_tut) / n * 100

    if pos_pct >= 70:
        regime = "🟢 **POZITIF PIYASA REJIMI** - cogu hisse alim/tutma bandinda."
    elif pos_pct >= 50:
        regime = "🟡 **KARISIK PIYASA** - secici olmak gerekiyor."
    elif n_dikkat >= n / 3:
        regime = "🔴 **RISK MODU** - savunmaci pozisyon onerilir."
    else:
        regime = "⏸️ **BEKLEME REJIMI** - katalist bekleniyor."

    return {
        "counts": counts,
        "avg_master_score": avg_master,
        "avg_confidence_10y": avg_conf,
        "strongest": strongest,
        "weakest": weakest,
        "regime_text": regime,
        "n_tickers": len(briefs),
    }
