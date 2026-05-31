"""
milestones.py - Hisse bazli kilometre tasi (timeline) veritabani.
Statik DB + haber akisindan dinamik cimbiz.
"""
from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

# Bilinen statik milestone'lar
STATIC_MILESTONES: dict[str, list[dict]] = {
    "IONQ": [
        {"date": "2024-09-30", "event": "Tempo - 64 qubit ticari sistem", "tag": "Tekno"},
        {"date": "2025-12-31", "event": "AQ 64 hedefi (Algoritmic Qubit)", "tag": "Roadmap"},
        {"date": "2026-12-31", "event": "Forte Enterprise (AQ 64+) genel kullanim", "tag": "Roadmap"},
        {"date": "2028-12-31", "event": "AQ 256 (broad quantum advantage hedefi)", "tag": "Roadmap"},
        {"date": "2030-12-31", "event": "AQ 1024 - hata duzeltmeli sistem", "tag": "Roadmap"},
    ],
    "RGTI": [
        {"date": "2024-12-31", "event": "84 qubit Ankaa-3 (>%99 2Q fidelity)", "tag": "Tekno"},
        {"date": "2025-12-31", "event": "100+ qubit modular sistem", "tag": "Roadmap"},
        {"date": "2027-06-30", "event": "1000+ qubit hedefi", "tag": "Roadmap"},
    ],
    "WOLF": [
        {"date": "2025-06-30", "event": "Mohawk Valley fab tam kapasite (200mm SiC wafer)", "tag": "Uretim"},
        {"date": "2025-12-31", "event": "Siler City SiC malzeme tesisi devreye almasi", "tag": "Uretim"},
        {"date": "2026-12-31", "event": "200mm SiC wafer pazar payi hedefi", "tag": "Pazar"},
    ],
    "ATOM": [
        {"date": "2024-12-31", "event": "GaN-on-SiC RF urunleri uretim asamasi", "tag": "Tekno"},
        {"date": "2025-12-31", "event": "Yeni RF guc amplifikator ailesi", "tag": "Urun"},
    ],
    "LAES": [
        {"date": "2024-12-31", "event": "SEALSQ post-kuantum kripto cipleri", "tag": "Tekno"},
        {"date": "2025-12-31", "event": "Quantum-safe IoT cip seri uretim", "tag": "Roadmap"},
    ],
    "AXTI": [
        {"date": "2024-12-31", "event": "InP wafer kapasite genislemesi", "tag": "Uretim"},
        {"date": "2025-12-31", "event": "GaAs ve InP yeni mussteri kazanimlari", "tag": "Pazar"},
    ],
    "NVTS": [
        {"date": "2025-06-30", "event": "GaN guc cipleri data center segmenti", "tag": "Pazar"},
        {"date": "2026-12-31", "event": "AI server icin yuksek voltaj GaN", "tag": "Roadmap"},
    ],
    "QUBT": [
        {"date": "2025-12-31", "event": "TFLN modulator urun ailesi genisleme", "tag": "Tekno"},
        {"date": "2026-12-31", "event": "Fotonik nucleer / Reservoir bilgisayar", "tag": "Roadmap"},
    ],
    "INDI": [
        {"date": "2025-06-30", "event": "Indie ADAS SoC seri uretim - global OEM'ler", "tag": "Pazar"},
        {"date": "2026-06-30", "event": "EV-spesifik radar/lidar SoC ramp", "tag": "Urun"},
        {"date": "2027-12-31", "event": "$1B+ yillik gelir hedefi", "tag": "Roadmap"},
    ],
    "ASML": [
        {"date": "2025-12-31", "event": "High-NA EUV ilk muşteri sevkıyatı (Intel)", "tag": "Tekno"},
        {"date": "2026-12-31", "event": "High-NA EUV volume ramp (TSMC/Samsung)", "tag": "Uretim"},
        {"date": "2027-12-31", "event": "EXE:5200 yeni nesil litografi", "tag": "Roadmap"},
        {"date": "2030-12-31", "event": "Hyper-NA EUV roadmap (sub-1nm)", "tag": "Roadmap"},
    ],
    # Cin (Hong Kong listings)
    "0981.HK": [
        {"date": "2024-12-31", "event": "SMIC 7nm ramp - Huawei Kirin 9000s", "tag": "Tekno"},
        {"date": "2025-12-31", "event": "5nm cip ureticilik denemesi (DUV multi-patterning)", "tag": "Tekno"},
        {"date": "2026-12-31", "event": "300mm wafer kapasite genislemesi", "tag": "Uretim"},
        {"date": "2028-12-31", "event": "Cin yerli litografi (SMEE) ile 3nm denemesi", "tag": "Roadmap"},
    ],
    "1347.HK": [
        {"date": "2025-06-30", "event": "Wuxi 12-inch fab Phase 2 ramp", "tag": "Uretim"},
        {"date": "2026-12-31", "event": "Otomotiv ve guc cipleri uretim payi artisi", "tag": "Pazar"},
        {"date": "2028-12-31", "event": "28nm/22nm mature node kapasite", "tag": "Roadmap"},
    ],
}

# Haberden cimbiz - regex pattern -> etiket
DYNAMIC_PATTERNS = [
    (r"(?i)\bAQ\s?(\d+)", "AQ Hedef"),
    (r"(?i)(\d+)\s?qubits?\b", "Qubit Aciklama"),
    (r"(?i)new\s+fab(rication)?|fab\s+opening", "Fab Acilisi"),
    (r"(?i)mass\s+production|volume\s+production", "Seri Uretim"),
    (r"(?i)contract\s+(award|win|secured)|awarded\s+contract", "Kontrat"),
    (r"(?i)darpa|department\s+of\s+defense|nasa", "Kamu/Savunma Kontrati"),
    (r"(?i)acquisition|merge[rd]?\b", "M&A"),
    (r"(?i)partnership\s+with|strategic\s+partnership", "Ortaklik"),
    (r"(?i)200mm\s+(SiC|wafer)", "200mm SiC"),
    (r"(?i)indium\s+phosphide|gallium\s+arsenide", "Materyal Atilim"),
    (r"(?i)export\s+control|export\s+ban|sanction", "Ihracat Kisiti"),
]


def _safe_parse_date(val) -> pd.Timestamp:
    """
    Herhangi bir formati (timestamp, epoch, datetime, string, None) ->
    valid pd.Timestamp.

    pandas 2.x'te 'Addition/subtraction of integers and integer-arrays with
    Timestamp is no longer supported' hatasini onlemek icin tum tarih
    parse'lari buradan gecer.
    """
    if val is None or val == "":
        return pd.Timestamp.now().normalize()
    try:
        if isinstance(val, pd.Timestamp):
            return val.tz_localize(None) if val.tz else val
        if isinstance(val, datetime):
            return pd.Timestamp(val)
        if isinstance(val, (int, float)):
            # Epoch: ms ise > 10^12, s ise ~10^9
            if val > 1e12:
                return pd.Timestamp(val, unit="ms")
            if val > 1e9:
                return pd.Timestamp(val, unit="s")
            return pd.Timestamp.now().normalize()
        s = str(val).strip()
        if not s:
            return pd.Timestamp.now().normalize()
        # ISO 8601 + zaman dilimi varyasyonlari
        ts = pd.to_datetime(s, errors="coerce", utc=True)
        if pd.isna(ts):
            ts = pd.to_datetime(s[:10], errors="coerce")
        if pd.isna(ts):
            return pd.Timestamp.now().normalize()
        return ts.tz_localize(None) if ts.tz else ts
    except Exception:
        return pd.Timestamp.now().normalize()


def extract_from_news(news_items: list[dict]) -> list[dict]:
    """Haberlerden dinamik milestone'lari cikar."""
    events = []
    for item in news_items or []:
        text = f"{item.get('title','')} {item.get('summary','')}"
        for pattern, tag in DYNAMIC_PATTERNS:
            try:
                m = re.search(pattern, text)
            except re.error:
                continue
            if m:
                snippet = item.get('title', '')[:140]
                pub = (item.get('published')
                       or item.get('providerPublishTime')
                       or item.get('pubDate'))
                ts = _safe_parse_date(pub)
                events.append({
                    "date": ts,
                    "event": snippet,
                    "tag": tag,
                    "source": "Haber",
                })
                break  # ayni haberi bir defa say
    return events


def get_timeline(ticker: str, news_items: list[dict] | None = None) -> pd.DataFrame:
    """
    Statik DB + haberlerden dinamik milestone listesini birlestir,
    DataFrame dondur (date sirali).

    Tum tarihler _safe_parse_date'ten gecer; integer-Timestamp aritmetik
    hatasi olmaz.
    """
    events = []
    for e in STATIC_MILESTONES.get(ticker.upper(), []):
        e = dict(e)
        e["date"] = _safe_parse_date(e.get("date"))
        e.setdefault("source", "DB")
        events.append(e)
    if news_items:
        events.extend(extract_from_news(news_items))
    if not events:
        return pd.DataFrame(columns=["date", "event", "tag", "source"])
    df = pd.DataFrame(events)
    # _safe_parse_date'ten gecmis olsa bile son kontrol
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df
