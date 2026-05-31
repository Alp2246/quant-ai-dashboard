"""
moonshot_detector.py - Moonshot Candidates J-Curve dedektoru.

Adaylar (kullanici talebi):  NVTS, INDI, RGTI
(Genisletilebilir: ATOM, LAES, AXTI - speculative ama 'sicrama' adaylari)

ALGORITMA - Sadece fiyat artisina bakma; uc finansal sinyali izle:
  1) Revenue Multiplier (gelir carpani)  - YoY revenue growth
  2) Backlog Growth                       - inventory / receivables proxy
  3) J-Curve (Ar-Ge + Revenue paralel artis)
      -> Eğer R&D harcamasi ve gelir paralel olarak hızlı buyuyorsa
         (siro kayip, sonradan exponential) -> KLASIK MOONSHOT pattern

Master Score'a +20 'SICRAMA POTANSIYELI' bonusu.

Kaynaklar:
  - yfinance income statement (R&D, Revenue)
  - yfinance balance sheet (Inventory, Receivables - backlog proxy)
  - quarterly + annual periodlari kiyaslar
"""
from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# Moonshot adaylari - kullanici talebi
MOONSHOT_CANDIDATES = {"NVTS", "INDI", "RGTI", "QBTS", "CRDO", "ALAB", "POET"}
# Yan adaylar (speculative ama sicrama profili - ek olarak izlenir)
SECONDARY_MOONSHOT = {
    "ATOM", "LAES", "IONQ", "QUBT", "AXTI", "AMBA", "ARQQ", "SMCI",
}


def _safe_first(df: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    """Quarterly/annual financials icinden olasi satir adlarini ara."""
    if df is None or df.empty:
        return None
    for c in candidates:
        for idx in df.index:
            if str(idx).lower().strip() == c.lower().strip():
                return df.loc[idx]
    # Partial match
    for c in candidates:
        for idx in df.index:
            if c.lower() in str(idx).lower():
                return df.loc[idx]
    return None


def _yoy_growth(series: pd.Series) -> float | None:
    """Son periyodun bir yil oncesine gore yuzde buyumesi."""
    if series is None or series.empty or len(series) < 2:
        return None
    try:
        clean = series.dropna()
        if len(clean) < 2:
            return None
        latest = float(clean.iloc[0])
        prior = float(clean.iloc[1])
        if prior == 0:
            return None
        if prior < 0 and latest < 0:
            return (abs(prior) - abs(latest)) / abs(prior) * 100
        return (latest - prior) / abs(prior) * 100
    except Exception:
        return None


@lru_cache(maxsize=64)
def detect_moonshot(ticker: str) -> dict:
    """
    Bir hissenin J-Curve sicrama profilinde olup olmadigini olc.

    Returns:
      {
        ticker,
        is_moonshot_candidate: bool,
        revenue_yoy_pct, rd_yoy_pct,
        revenue_multiplier (2y/3y comp),
        backlog_growth_pct,
        j_curve_score (0..100),
        master_bonus (-5..+20),
        labels: list[str],
        rationale: str,
      }
    """
    ticker_u = ticker.upper()
    is_primary = ticker_u in MOONSHOT_CANDIDATES
    is_secondary = ticker_u in SECONDARY_MOONSHOT

    out = {
        "ticker": ticker_u,
        "is_moonshot_candidate": is_primary or is_secondary,
        "is_primary_moonshot": is_primary,
        "revenue_yoy_pct": None, "rd_yoy_pct": None,
        "revenue_multiplier": None, "backlog_growth_pct": None,
        "j_curve_score": 0, "master_bonus": 0,
        "labels": [], "rationale": "",
    }
    if not (is_primary or is_secondary):
        return out

    try:
        tk = yf.Ticker(ticker_u)
        income = tk.financials
        income_q = tk.quarterly_financials
        balance = tk.balance_sheet
    except Exception as e:
        logger.debug("moonshot fetch %s: %s", ticker_u, e)
        out["rationale"] = f"yfinance erisim hatasi: {e}"
        return out

    # ---- Revenue YoY (annual + quarterly) ----
    rev_a = _safe_first(income, ["Total Revenue", "Revenue", "Operating Revenue"])
    rev_q = _safe_first(income_q, ["Total Revenue", "Revenue"])
    rev_yoy = _yoy_growth(rev_q) if rev_q is not None else _yoy_growth(rev_a)
    out["revenue_yoy_pct"] = round(rev_yoy, 1) if rev_yoy is not None else None

    # Revenue Multiplier: 2 yil oncesine gore
    if rev_a is not None and len(rev_a.dropna()) >= 3:
        clean = rev_a.dropna()
        try:
            r_now = float(clean.iloc[0])
            r_2y = float(clean.iloc[2])
            if r_2y > 0:
                mult = r_now / r_2y
                out["revenue_multiplier"] = round(mult, 2)
        except Exception:
            pass

    # ---- R&D YoY (J-Curve sinyali) ----
    rd_a = _safe_first(income, ["Research And Development",
                                  "Research Development",
                                  "Research & Development"])
    rd_q = _safe_first(income_q, ["Research And Development",
                                    "Research Development"])
    rd_yoy = _yoy_growth(rd_q) if rd_q is not None else _yoy_growth(rd_a)
    out["rd_yoy_pct"] = round(rd_yoy, 1) if rd_yoy is not None else None

    # ---- Backlog Growth (inventory + receivables proxy) ----
    inv = _safe_first(balance, ["Inventory", "Inventories", "Net Inventory"])
    rec = _safe_first(balance, ["Net Receivables", "Receivables",
                                  "Accounts Receivable",
                                  "Trade Receivables"])
    backlog_series = None
    if inv is not None and rec is not None:
        try:
            inv_c = inv.dropna()
            rec_c = rec.dropna()
            aligned = pd.concat([inv_c, rec_c], axis=1).dropna()
            if len(aligned) >= 2:
                aligned["backlog"] = aligned.iloc[:, 0] + aligned.iloc[:, 1]
                backlog_series = aligned["backlog"]
        except Exception:
            pass
    elif rec is not None:
        backlog_series = rec.dropna()
    if backlog_series is not None and len(backlog_series) >= 2:
        bg = _yoy_growth(backlog_series)
        out["backlog_growth_pct"] = round(bg, 1) if bg is not None else None

    # ---- J-CURVE SKORU (0..100) ----
    score = 0.0
    labels = []

    rev_y = out["revenue_yoy_pct"]
    rd_y = out["rd_yoy_pct"]
    bg = out["backlog_growth_pct"]
    mult = out["revenue_multiplier"]

    # 1) Revenue YoY > %30 ise +25, > %15 ise +15, > %5 ise +5
    if rev_y is not None:
        if rev_y >= 50:
            score += 30; labels.append(f"📈 Revenue YoY +{rev_y:.0f}% (patlama)")
        elif rev_y >= 30:
            score += 25; labels.append(f"📈 Revenue YoY +{rev_y:.0f}%")
        elif rev_y >= 15:
            score += 15; labels.append(f"📈 Revenue YoY +{rev_y:.0f}%")
        elif rev_y >= 5:
            score += 5
        elif rev_y < -10:
            score -= 10; labels.append(f"📉 Revenue daralma {rev_y:.0f}%")

    # 2) Revenue Multiplier (2y) > 2.0x -> +20
    if mult is not None:
        if mult >= 3.0:
            score += 25; labels.append(f"⚡ 2y Revenue {mult:.1f}x")
        elif mult >= 2.0:
            score += 20; labels.append(f"⚡ 2y Revenue {mult:.1f}x")
        elif mult >= 1.5:
            score += 10

    # 3) R&D YoY > %20 ise +20 (J-Curve - yatirim devam ediyor)
    if rd_y is not None:
        if rd_y >= 30:
            score += 25; labels.append(f"🔬 R&D YoY +{rd_y:.0f}% (J-Curve)")
        elif rd_y >= 20:
            score += 20; labels.append(f"🔬 R&D YoY +{rd_y:.0f}%")
        elif rd_y >= 10:
            score += 10
        elif rd_y < -10:
            score -= 5; labels.append(f"R&D kesintisi {rd_y:.0f}%")

    # 4) Backlog Growth > %25 -> +15 (sipariş defteri patliyor)
    if bg is not None:
        if bg >= 50:
            score += 20; labels.append(f"📦 Backlog/Receivables +{bg:.0f}%")
        elif bg >= 25:
            score += 15; labels.append(f"📦 Backlog +{bg:.0f}%")
        elif bg >= 10:
            score += 8
        elif bg < -20:
            score -= 5

    score = max(0, min(100, score))
    out["j_curve_score"] = round(score, 1)

    # ---- Master Score bonusu (-5..+20) ----
    # Kullanici talebi: J-Curve onayli ise +20 'SICRAMA POTANSIYELI'
    if score >= 65:
        bonus = 20
        labels.insert(0, "🚀 SICRAMA POTANSIYELI (+20 MASTER)")
        rationale = ("J-Curve onayli: Revenue + R&D paralel buyume + "
                       "backlog patlamasi.")
    elif score >= 45:
        bonus = 12
        labels.insert(0, "📈 Gucu artan sicrama profili (+12)")
        rationale = "Pozitif J-Curve sinyalleri, henuz tam onaylanmadi."
    elif score >= 25:
        bonus = 5
        labels.insert(0, "🟢 Hafif sicrama sinyali (+5)")
        rationale = "Erken donem J-Curve emareleri."
    elif score <= 5 and (rev_y is not None and rev_y < 0):
        bonus = -5
        labels.insert(0, "⚠️ Moonshot adayinda finansal yorgunluk")
        rationale = "Gelir daralmasi + zayif buyume - J-Curve kirildi."
    else:
        bonus = 0
        rationale = "Yetersiz veya notr J-Curve sinyali."

    out["master_bonus"] = bonus
    out["labels"] = labels
    out["rationale"] = rationale

    return out


def get_explosive_factor(ticker: str) -> str:
    """
    Investor Overview tablosu icin tek-satir 'Explosive Factor' etiketi
    (kullanici talebi).
    """
    t = ticker.upper()
    return EXPLOSIVE_FACTOR.get(t, "-")


# Hisse -> insan-okunabilir 'Patlama Faktoru' (Investor Overview kolonu)
EXPLOSIVE_FACTOR: dict[str, str] = {
    # Kullanici talebi
    "LAES": "⚡ Cyber-Armageddon Demand (Q-Day PQC patlamasi)",
    "NVTS": "⚡ GaN/SiC Adoption - Tier-1 OEM esigi (Tesla/VW/Hyundai)",
    "INDI": "⚡ Autonomous SoC Win (L3+ FSD design wins)",
    "RGTI": "⚡ Superconducting Quantum Scale (1K+ qubit roadmap)",
    # Diger hisseler
    "IONQ": "⚡ Logical Qubit / AQ Roadmap (Enterprise quantum)",
    "ATOM": "⚡ MST Foundry Royalty (lisans-her-wafer)",
    "WOLF": "⚡ Mohawk Valley SiC ramp (EV megacycle)",
    "ASML": "⚡ High-NA EUV monopoly (2nm node)",
    "AXTI": "⚡ InP demand spike (silicon photonics + 800G optic)",
    "QUBT": "⚡ Photonic quantum networking (defense)",
    "0981.HK": "⚡ China 7nm self-sufficiency",
    "NVDA": "⚡ AI infrastructure dominance (CUDA moat)",
    "QBTS": "⚡ Quantum Annealing Enterprise (Advantage2 cloud)",
    "CRDO": "⚡ 800G AEC AI Rack Interconnect (hyperscaler win)",
    "ALAB": "⚡ PCIe Gen6 / CXL Retimer (AI fabric scaling)",
    "AEHR": "⚡ SiC/GaN Test Ramp (pickaxe - WOLF/NVTS proxy)",
    "POET": "⚡ Silicon Photonics 800G Engine (optical JDA)",
    "AVGO": "⚡ Custom XPU ASIC (Google/Meta hyperscaler)",
    "MRVL": "⚡ Custom AI Silicon + Electro-Optics",
    "VRT": "⚡ AI DC Power & Liquid Cooling Capex",
    "MU": "⚡ HBM3E Allocation (Blackwell memory stack)",
    "LSCC": "⚡ Edge AI FPGA Design Win",
    "ARM": "⚡ v9 / Neoverse Royalty-per-Chip",
    "ARQQ": "⚡ PQC SaaS Government Mandate (Q-Day)",
    "PLTR": "⚡ DoD + Enterprise AIP Deployment",
    "AMBA": "⚡ Automotive Vision SoC Tier-1 Win",
    "SMCI": "⚡ GB200 AI Server Volume Shipment",
}
