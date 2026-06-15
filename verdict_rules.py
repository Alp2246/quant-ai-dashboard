"""
verdict_rules.py - TEK KAYNAK karar kurali (single source of truth).

Tum uygulamada (dashboard tablosu, Master Score, Telegram, Alpha Engine)
ayni skor -> ayni aksiyon etiketi cikar. Boylece "96 skor ama BEKLE" gibi
celiskiler olmaz.

Kullanim:
    from verdict_rules import verdict_for, VERDICT_COLORS, VERDICT_EMOJI

    v = verdict_for(master_score=96.2)          # -> "KRITIK ALIM"
    v = verdict_for(master_score=48, cash_unsustainable=True)  # -> "DIKKAT"
"""
from __future__ import annotations

# Skor bandlari: (alt_esik, etiket). Yuksekten dusuge sirali.
# master_score.py ile BIREBIR ayni esikler.
VERDICT_BANDS: list[tuple[float, str]] = [
    (85, "KRITIK ALIM"),
    (70, "GUCLU AL"),
    (55, "AL"),
    (40, "BEKLE"),
    (25, "DIKKAT"),
    (0,  "SAT"),
]

VERDICT_COLORS: dict[str, str] = {
    "KRITIK ALIM": "#d500f9",
    "GUCLU AL":    "#00c853",
    "AL":          "#69f0ae",
    "BEKLE":       "#ffc107",
    "DIKKAT":      "#ff9100",
    "SAT":         "#ff1744",
}

VERDICT_EMOJI: dict[str, str] = {
    "KRITIK ALIM": "🚨",
    "GUCLU AL":    "✅",
    "AL":          "🟢",
    "BEKLE":       "🟡",
    "DIKKAT":      "🟠",
    "SAT":         "🔴",
}

# Telegram / bildirim icin: bu etiketlerde telefona push gonderilir.
PUSH_VERDICTS: set[str] = {"KRITIK ALIM", "GUCLU AL"}


def verdict_for(
    master_score: float,
    *,
    cash_unsustainable: bool = False,
    critical_alert: bool = False,
    confidence: float | None = None,
) -> str:
    """
    Master Score'tan TEK aksiyon etiketi uretir.

    Master Score birincil suruculdur. Guvenlik gerekceleri (nakit bitti,
    kritik tedarik zinciri uyarisi) sonucu asagi ceker ama YUKARI cekmez.
    confidence yalnizca bilgi amaclidir; etiketi degistirmez (tutarlilik).
    """
    label = "SAT"
    for threshold, name in VERDICT_BANDS:
        if master_score >= threshold:
            label = name
            break

    # Guvenlik override'lari: sadece asagi ceker
    if cash_unsustainable or critical_alert:
        if label in ("KRITIK ALIM", "GUCLU AL", "AL"):
            return "DIKKAT"
        if label == "BEKLE":
            return "DIKKAT"
    return label


def is_push_worthy(verdict: str) -> bool:
    """Bu verdict telefona bildirim gonderilmeye deger mi?"""
    return verdict in PUSH_VERDICTS


def color_for(verdict: str) -> str:
    return VERDICT_COLORS.get(verdict, "#888")


def emoji_for(verdict: str) -> str:
    return VERDICT_EMOJI.get(verdict, "")
