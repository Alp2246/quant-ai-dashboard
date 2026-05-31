"""
competitor_benchmark.py - Rakip Kıyaslama (Relative Strength) modulu.

AXT (AXTI) icin global compound-semi rakipleri:
  - IQE plc (IQEP.L)  - InP/GaAs epitaxy lideri (UK borsasi, Londra)
  - Sumitomo Electric (5802.T) - Japonya InP wafer ureticisi
  - II-VI / Coherent (COHR) - genis spektrum compound semi

Mantik (kullanici talebi):
  AXTI Master Score'u hesaplanirken; eger AXTI rakiplerden gocebilen pay
  kazaniyorsa (IQE dusuyor, AXTI artiyorsa) -> 'Stratejik Buyume' bonusu.
  Tersine eger rakipler patliyor ve AXTI geride kaliyorsa -> ceza.

Cikti `master_score`'a 'strategic_overlay_bonus' uzerinden geclir.
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# Hisse -> rakip kumesi (genisletilebilir)
COMPETITOR_GROUPS: dict[str, list[str]] = {
    # AXT (InP/GaAs/Ge) -> IQE plc + Sumitomo Electric + Coherent
    "AXTI":  ["IQE.L", "5802.T", "COHR"],
    # SEALSQ (PQC HW) -> Infineon, NXP, STMicro (Secure Element rakipleri)
    "LAES":  ["IFX.DE", "NXPI", "STM"],
    # Wolfspeed -> on Semi, II-VI (SiC rakipleri)
    "WOLF":  ["ON", "COHR", "STM"],
    # ASML -> ek lithography rakipleri (Canon, Nikon)
    "ASML":  ["CAJ", "7731.T"],
    # Atomera -> none (niche IP)
    # NVTS (GaN Power) -> Infineon (GaN/Si), Power Integrations, onsemi,
    # Transphorm (LSE: TGAN delisted -> EPC unlisted; STM GaN da rakip)
    "NVTS":  ["IFX.DE", "POWI", "STM", "ON"],
    # INDI (Automotive SoC) -> Mobileye, NXP, Ambarella, Texas Instruments
    "INDI":  ["MBLY", "NXPI", "AMBA", "TXN"],
    # QUBT (Photonic Quantum) -> Lightmatter (yok), IonQ, RGTI, MicroVision
    "QUBT":  ["IONQ", "RGTI"],
    # QBTS (Quantum Annealing) -> IONQ, RGTI (farkli fizik ama kuantum sepeti)
    "QBTS":  ["IONQ", "RGTI", "IBM"],
    # CRDO (AEC) -> Marvell, Broadcom networking
    "CRDO":  ["MRVL", "AVGO", "CIEN"],
    # ALAB (Retimer) -> Parade, Montage, Rambus
    "ALAB":  ["PSMT", "RMBS", "MRVL"],
    # AEHR (Test) -> Teradyne, Advantest (ADR)
    "AEHR":  ["TER", "ATEYY"],
    # POET (SiPho) -> Lumentum, Coherent
    "POET":  ["LITE", "COHR"],
    # AVGO custom ASIC -> Marvell, AMD
    "AVGO":  ["MRVL", "AMD", "NVDA"],
    "MRVL":  ["AVGO", "AMD", "NVDA"],
    # VRT DC infra -> Schneider, Eaton
    "VRT":   ["ETN", "SU.PA"],
    # MU HBM -> SK Hynix ADR
    "MU":    ["000660.KS"],
    # ARM IP -> RISC-V pure plays proxy
    "ARM":   ["NVDA", "QCOM"],
    # ARQQ PQC SaaS -> LAES HW proxy + CRWD
    "ARQQ":  ["CRWD", "PANW"],
    # PLTR -> SNOW, MSFT (enterprise AI)
    "PLTR":  ["SNOW", "MSFT"],
    # SMCI AI server -> Dell, HPE
    "SMCI":  ["DELL", "HPE"],
}


def _fetch_returns(symbol: str, days: int = 120) -> pd.Series | None:
    try:
        df = yf.Ticker(symbol).history(period=f"{int(days*1.6)}d",
                                          auto_adjust=False)
        if df.empty or "Close" not in df.columns:
            return None
        c = df["Close"].dropna().tail(days)
        if len(c) < 30:
            return None
        return c
    except Exception as e:
        logger.debug("fetch %s: %s", symbol, e)
        return None


def relative_strength(ticker: str, days: int = 120) -> dict:
    """
    Hisse vs rakip kumesi getiri farki.

    Returns:
      {
        ticker, competitors, days,
        ticker_return_pct, competitor_avg_return_pct,
        relative_strength_pp,   # AXTI - rakip ort. (yuzde puan)
        bonus,                  # master score'a eklenir (-15..+15)
        label,
        narrative,
        per_competitor: {sym: ret_pct},
      }
    """
    comps = COMPETITOR_GROUPS.get(ticker.upper(), [])
    if not comps:
        return {"ticker": ticker, "bonus": 0, "label": "RAKIP YOK",
                "competitors": [], "narrative": ""}

    tser = _fetch_returns(ticker, days)
    if tser is None or len(tser) < 30:
        return {"ticker": ticker, "bonus": 0, "label": "VERI YETERSIZ",
                "competitors": comps, "narrative": "Yetersiz fiyat verisi"}

    t_ret = (float(tser.iloc[-1]) / float(tser.iloc[0]) - 1.0) * 100

    per_comp = {}
    for sym in comps:
        cs = _fetch_returns(sym, days)
        if cs is None:
            continue
        cr = (float(cs.iloc[-1]) / float(cs.iloc[0]) - 1.0) * 100
        per_comp[sym] = round(cr, 2)

    if not per_comp:
        return {"ticker": ticker, "bonus": 0, "label": "RAKIP VERI YOK",
                "competitors": comps,
                "ticker_return_pct": round(t_ret, 2),
                "narrative": "Rakip fiyat verisi alinamadi"}

    comp_avg = float(np.mean(list(per_comp.values())))
    rs = t_ret - comp_avg  # yuzde puan farki

    # Bonus mantigi (kullanici talebi):
    # AXTI artiyor, rakip dusuyorsa STRATEJIK BUYUME = +15
    # Hafif goreceli guc = +5..+10
    # Goreceli zayiflik = -5..-15
    tk = ticker.upper()
    if rs >= 30 and t_ret > 0 and comp_avg < 0:
        bonus = 15
        label = f"🚀 STRATEJIK BUYUME ({tk} pay aliyor)"
        narr = (f"{tk} {t_ret:+.1f}% getiri, rakip ort. {comp_avg:+.1f}%. "
                  f"Goreceli guc {rs:+.1f}pp - rakiplerden pazar payi aliyor.")
    elif rs >= 15:
        bonus = 10
        label = "💪 GORECELI GUC"
        narr = (f"{tk} rakip ortalamasindan {rs:+.1f}pp daha iyi. "
                  f"Pozitif momentum.")
    elif rs >= 5:
        bonus = 5
        label = "🟢 HAFIF GORECELI GUC"
        narr = f"{tk} rakip ortalamasindan {rs:+.1f}pp daha iyi."
    elif rs <= -30 and t_ret < 0 and comp_avg > 0:
        bonus = -15
        label = "📉 STRATEJIK ZAYIFLIK"
        narr = (f"{tk} {t_ret:+.1f}%, rakip ort. {comp_avg:+.1f}%. "
                  f"Goreceli zayiflik {rs:+.1f}pp - rakipler pay aliyor.")
    elif rs <= -15:
        bonus = -10
        label = "🔴 GORECELI ZAYIFLIK"
        narr = f"{tk} rakip ortalamasindan {rs:+.1f}pp geride."
    elif rs <= -5:
        bonus = -5
        label = "🟠 HAFIF GORECELI ZAYIFLIK"
        narr = f"{tk} rakip ortalamasindan {rs:+.1f}pp geride."
    else:
        bonus = 0
        label = "⚖️ DENGE"
        narr = f"{tk} ve rakipler birbirine yakin ({rs:+.1f}pp fark)."

    return {
        "ticker": ticker,
        "competitors": comps,
        "days": days,
        "ticker_return_pct": round(t_ret, 2),
        "competitor_avg_return_pct": round(comp_avg, 2),
        "relative_strength_pp": round(rs, 2),
        "bonus": bonus,
        "label": label,
        "narrative": narr,
        "per_competitor": per_comp,
    }
