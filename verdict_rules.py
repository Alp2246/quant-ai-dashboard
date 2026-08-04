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


def gated_verdict(
    final_score: float,
    *,
    market_status: str = "UNKNOWN",
    is_overfit: bool = False,
    fund_status: str = "PASS",
    pr_only: bool = False,
    cash_unsustainable: bool = False,
    critical_alert: bool = False,
) -> tuple[str, list[str]]:
    """Kapilardan gecmis skordan verdict uretir. (verdict, sebepler)

    NEDEN AYRI FONKSIYON (olculmus vaka — LAES 02.08.2026):
    verdict_for yalnizca cash_unsustainable/critical_alert ile asagi ceker.
    LAES'te "prob_up<0.5 VE fiyat<SMA50 VE marj -%187" ucu birden dogruyken
    "KRITIK ALIM" uretildi ve telefona push gitti. Overfit bilgisi
    hesaplaniyordu ama imzada YOKTU.

    Bu fonksiyon o bilgileri karara sokar. Kurallar YALNIZCA ASAGI ceker —
    hicbir kapi bir sembolu yukari tasiyamaz.
    """
    verdict = verdict_for(
        final_score,
        cash_unsustainable=cash_unsustainable,
        critical_alert=critical_alert,
    )
    sebepler: list[str] = []

    # Trend teyidi yoksa "KRITIK ALIM"/"GUCLU AL" YASAK — dip arayisi bandi
    if market_status == "FAIL" and verdict in ("KRITIK ALIM", "GUCLU AL"):
        verdict = "BEKLE"
        sebepler.append("Trend teyidi yok (fiyat SMA20 ve SMA50 altinda) "
                        "— dip arayisi/takip bandina indirildi")

    # Overfit model teyit sayilmaz
    if is_overfit and verdict in ("KRITIK ALIM", "GUCLU AL"):
        verdict = "AL" if verdict == "KRITIK ALIM" else "BEKLE"
        sebepler.append("Model siddetli overfit — tahmin teyit sayilmadi")

    # Temel FAIL veya salt PR: en yuksek band kapali
    if (fund_status == "FAIL" or pr_only) and verdict == "KRITIK ALIM":
        verdict = "GUCLU AL" if not pr_only else "BEKLE"
        sebepler.append("Temel dogrulama zayif / baglayici kanit yok "
                        "— KRITIK ALIM bandi kapali")

    return verdict, sebepler


def allow_push(
    verdict: str,
    *,
    market_status: str = "UNKNOWN",
    is_overfit: bool = False,
) -> tuple[bool, str | None]:
    """Telefona push gitsin mi? (izin, red_sebebi)

    String'i degistirmek YETMEZ — gercek push cagrisi da susmalidir.
    Bu yuzden push yolundaki her cagri noktasi bunu sorar.
    """
    if is_overfit:
        return False, "Model siddetli overfit — push bastirildi"
    if market_status == "FAIL":
        return False, "Trend teyidi yok (SMA20/SMA50 alti) — push bastirildi"
    if verdict not in PUSH_VERDICTS:
        return False, f"Verdict '{verdict}' push bandinda degil"
    return True, None


def is_push_worthy(verdict: str) -> bool:
    """Bu verdict telefona bildirim gonderilmeye deger mi?

    DIKKAT: bu YALNIZCA band kontroludur. Kapili karar icin allow_push()
    kullanin — overfit/trend vetosu burada YOKTUR.
    """
    return verdict in PUSH_VERDICTS


def color_for(verdict: str) -> str:
    return VERDICT_COLORS.get(verdict, "#888")


def emoji_for(verdict: str) -> str:
    return VERDICT_EMOJI.get(verdict, "")
