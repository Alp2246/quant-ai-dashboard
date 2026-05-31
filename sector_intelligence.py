"""
sector_intelligence.py - Sektorel bagimlilik haritasi.
NVDA AI talebi -> TSMC siparisi -> ASML EUV siparisi gibi zincirleri olc.

Beta-correlation ile makro hisselerin (NVDA, TSM, INTC) cekirdek
portfoyumuza (ASML, WOLF, IONQ vs.) etkisini hesapla.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# Sektorel zincirler: 'leader' -> ['follower1', 'follower2', ...]
SECTOR_CHAINS = {
    "AI_DEMAND": {
        "leaders": ["NVDA", "AMD"],
        "followers": ["TSM", "ASML", "WOLF", "NVTS"],
        "narrative": "AI cipi talebi -> foundry capex -> litografi siparisi",
    },
    "EUV_CYCLE": {
        "leaders": ["TSM", "INTC"],
        "followers": ["ASML", "ATOM"],
        "narrative": "Foundry buyume -> EUV makina siparisi (ASML tekel)",
    },
    "EV_POWER": {
        "leaders": ["TSLA", "BYDDF"],
        "followers": ["WOLF", "NVTS", "ATOM"],
        "narrative": "EV uretim -> SiC/GaN guc cipi talebi",
    },
    "QUANTUM_HYPE": {
        "leaders": ["IBM", "NVDA"],
        "followers": ["IONQ", "RGTI", "QUBT", "QBTS"],
        "narrative": "Buyuk teknoloji kuantum yatirimi -> pure-play kuantum",
    },
    "AI_INTERCONNECT": {
        "leaders": ["NVDA", "MSFT", "META"],
        "followers": ["CRDO", "ALAB", "POET", "AXTI"],
        "narrative": ("AI rack bandwidth -> AEC/PCIe-CXL retimer + "
                       "silicon photonics optical engine."),
    },
    "AI_DC_BUILDOUT": {
        "leaders": ["NVDA", "MSFT", "GOOGL"],
        "followers": ["VRT", "SMCI", "NVTS", "MU"],
        "narrative": ("Hyperscaler AI capex -> rack power/cooling + HBM + "
                       "GaN power semi."),
    },
    "CUSTOM_XPU": {
        "leaders": ["GOOGL", "META", "AMZN"],
        "followers": ["AVGO", "MRVL", "ARM"],
        "narrative": ("Hyperscaler custom AI chip -> ASIC vendor + CPU IP "
                       "royalty."),
    },
    "SEMI_TEST_RAMP": {
        "leaders": ["WOLF", "NVTS", "ON"],
        "followers": ["AEHR"],
        "narrative": ("SiC/GaN production ramp -> wafer-level burn-in/test "
                       "equipment demand (AEHR pickaxe)."),
    },
    "CHINA_TECH_WAR": {
        "leaders": ["TSM", "ASML", "AMAT"],
        "followers": ["0981.HK", "1347.HK", "AXTI"],
        "narrative": "ABD ihracat kontrolu -> Cin yerli cip ekosistemi",
        "inverse": True,  # tetikleyici dustugunde follower yukselir
    },
    "EV_POWER_EFFICIENCY": {
        # NVTS (GaN) ozelinde EV verim odakli zincir.
        # Tier-1 OEM (Tesla, VW, Hyundai/Kia, Stellantis) hareketi
        # GaN/SiC adaptasyonunu hizlandirir.
        "leaders": ["TSLA", "VWAGY", "HYMTF", "STLA"],
        "followers": ["NVTS", "WOLF"],
        "narrative": ("Tier-1 OEM EV uretim hizi -> GaN/SiC verim cipi talebi "
                       "(NVTS, WOLF)."),
    },
    "AI_DATACENTER_POWER": {
        # NVDA + hyperscaler veri merkezi guc ihtiyaci -> 48V GaN power supply
        "leaders": ["NVDA", "AMD", "MSFT", "META"],
        "followers": ["NVTS", "MPWR", "VRT"],
        "narrative": ("AI veri merkezi guc dansitesi -> GaN bazli yuksek-verim "
                       "guc kaynaklari (NVTS 48V). NVDA rack-scale GPU = NVTS "
                       "icin direkt katalist."),
    },
    "SECURITY_IP": {
        # Post-Quantum / IoT Security ekosistemi - SEALSQ (LAES) zinciri.
        # Q-Day yaklasimi ile cybersecurity CAPEX'inin patlamasi bekleniyor:
        #   - Liderler: PANW (Palo Alto), CRWD (CrowdStrike), CSCO (Cisco IoT)
        #   - Follower'lar: SEALSQ (LAES) hardware-level PQC
        # Cybersecurity harcamasi artarsa SEALSQ ruzgardan yararlanir.
        "leaders": ["PANW", "CRWD", "CSCO"],
        "followers": ["LAES"],
        "narrative": "Cybersecurity CAPEX + Q-Day korkusu -> PQC hardware "
                       "secure element (SEALSQ).",
    },
}


def get_leader_movement(leaders: list[str], days: int = 30) -> dict:
    """Liderlerin son N gun getirisi."""
    rets = {}
    for sym in leaders:
        try:
            df = yf.Ticker(sym).history(period=f"{days*2}d")
            if df.empty:
                continue
            c = df["Close"].tail(days)
            if len(c) < 5:
                continue
            r = (float(c.iloc[-1]) / float(c.iloc[0]) - 1) * 100
            rets[sym] = round(r, 2)
        except Exception as e:
            logger.debug("%s leader fetch: %s", sym, e)
    return rets


def chain_signal(chain_key: str, days: int = 30) -> dict:
    """
    Bir zincir icin tetikleyicilerin ortalama getirisi -> follower hisselere
    pozitif/negatif rüzgar.
    """
    chain = SECTOR_CHAINS.get(chain_key)
    if not chain:
        return {}

    leader_rets = get_leader_movement(chain["leaders"], days)
    if not leader_rets:
        return {"chain": chain_key, "leader_avg_pct": 0, "signal": 0,
                "leader_rets": {}, "followers": chain["followers"],
                "narrative": chain["narrative"]}

    avg = float(np.mean(list(leader_rets.values())))
    if chain.get("inverse"):
        avg = -avg

    # avg %20'den fazla yukselirse +5; %20'den fazla duserse -5
    signal = max(-5, min(5, avg / 4))

    return {
        "chain": chain_key,
        "narrative": chain["narrative"],
        "leader_rets": leader_rets,
        "leader_avg_pct": round(avg, 2),
        "signal": round(signal, 2),
        "followers": chain["followers"],
        "inverse": chain.get("inverse", False),
    }


def scan_all_chains(days: int = 30) -> dict:
    """Tum sektorel zincirleri tara."""
    return {k: chain_signal(k, days) for k in SECTOR_CHAINS}


def derive_sector_weight(ticker: str, chains_data: dict) -> dict:
    """
    Bir hisseye gelen sektorel etki agirligi.
    Cikti: -5..+5 (Master Score'a etki).
    """
    total = 0.0
    chains_hit = []
    for k, data in chains_data.items():
        if not data:
            continue
        if ticker in data.get("followers", []):
            total += data.get("signal", 0)
            chains_hit.append({
                "chain": k,
                "narrative": data.get("narrative", ""),
                "signal": data.get("signal", 0),
                "leader_avg_pct": data.get("leader_avg_pct", 0),
                "leader_rets": data.get("leader_rets", {}),
            })

    # Kac zincire dahilse o kadar boluyoruz
    if chains_hit:
        total = total / len(chains_hit) * 1.5  # bonus catalyzator
    weight = max(-5, min(5, round(total, 2)))

    if weight >= 2:
        label = "🚀 SEKTOREL TETIKLEYICI POZITIF"
    elif weight >= 0.5:
        label = "📈 Sektorel Lehe"
    elif weight <= -2:
        label = "🔻 SEKTOREL TETIKLEYICI NEGATIF"
    elif weight <= -0.5:
        label = "📉 Sektorel Karsida"
    else:
        label = "➖ Sektorel Notr"

    return {
        "ticker": ticker,
        "sector_weight": weight,
        "label": label,
        "chains": chains_hit,
    }
