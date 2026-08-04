"""score_gate.py — Score_raw uzerine CARPIMSAL veto katmani.

NEDEN VAR (olculmus vaka — LAES, 02.08.2026):
compute_master_score additive calisir. LAES'te:
    taban 66.5 + stratejik +8 + moonshot +20 = 94.5 -> "KRITIK ALIM" -> PUSH
Ayni paketin icinde SU VARDI:
    - ml_model: prob_up=0.376 ("SAT"), overfit_verdict="SIDDETLI OVERFIT",
      CV dogruluk %51.6, train/CV gap 0.42
    - teknik  : fiyat < SMA20 < SMA50 (sma_pt=0)
    - temel   : net marj -%187, isletme nakit akisi -31.3M$
    - rakip   : 120 gunde -69pp goreceli zayiflik

Toplama islemi bu CELISKIYI uzlastirdi: -15 rakip cezasi ve sma_pt=0 kaybi,
tek kalemlik +20 moonshot ile silindi. Oysa celiskinin kendisi bilgidir.

CARPIMSAL yapi bunu YAPISAL olarak engeller: bir katmanin dusuk carpani
toplamda kaybolmaz, tum skoru olceklendirir.

    Final = Score_raw x M_market x M_overfit x M_fund

ONEMLI: compute_master_score'un additive formulu KORUNUR (silinmedi).
Bu modul onun CIKTISI uzerine kapi uygular. Panel additive kirilimi
gostermeye devam edebilir; karar ve push bu moduldeki final skora baglanir.
"""

from __future__ import annotations

from typing import Any

# --- Carpan degerleri (testte sabitlenmistir; degistirmek testi bozar) ---
M_MARKET_FAIL = 0.60      # fiyat hem SMA20 hem SMA50 altinda
M_OVERFIT_FAIL = 0.70     # SIDDETLI OVERFIT veya CV < 0.55
M_FUND_FAIL = 0.70        # nakit yakiyor + marj cok negatif + gelir daraliyor

CV_MIN_USABLE = 0.55      # bunun altinda model "yazi tura" sayilir
NET_MARGIN_FAIL_PCT = -50.0
HABER_KALDIRAC_TAVAN_ORANI = 0.40   # zayif temelde haber bonusunun max payi


def _norm(s: Any) -> str:
    return str(s or "").strip().upper()


def classify_market(technical: dict | None) -> tuple[float, str, str | None]:
    """M_market: fiyat trendi. (carpan, status, sebep)

    KURAL: fiyat HEM SMA20 HEM SMA50 altindaysa FAIL. Tek bir ortalamanin
    altinda olmak (orn. kisa vadeli geri cekilme) tek basina FAIL degildir —
    dip alimi stratejisini oldurmemek icin bilincli olarak boyle.
    """
    t = technical or {}
    close = t.get("close")
    sma20 = t.get("sma_20") or t.get("sma20")
    sma50 = t.get("sma_50") or t.get("sma50")

    if close is None or not sma20 or not sma50:
        return 1.0, "UNKNOWN", None       # veri yoksa ceza verme

    c, s20, s50 = float(close), float(sma20), float(sma50)
    if c < s20 and c < s50:
        return (M_MARKET_FAIL, "FAIL",
                f"Fiyat {c:.2f} hem SMA20 ({s20:.2f}) hem SMA50 ({s50:.2f}) altinda "
                f"— trend teyidi yok")
    return 1.0, "PASS", None


def classify_overfit(ml_result: dict | None) -> tuple[float, bool, str | None]:
    """M_overfit: ML guvenilirligi. (carpan, is_overfit, sebep)

    Bu bilgi ZATEN hesaplaniyordu (ml_model.py Lopez de Prado Purged CV)
    ama ne compute_master_score ne verdict_for imzasinda yer aliyordu —
    yani hesaplanip ATILIYORDU. Bu fonksiyon o bosluğu kapatir.
    """
    ml = ml_result or {}
    verdict = _norm(ml.get("overfit_verdict"))
    cv = ml.get("cv_mean_accuracy")

    siddetli = verdict.startswith("SIDDETLI") or verdict.startswith("ŞİDDETLİ")
    cv_zayif = cv is not None and float(cv) > 0 and float(cv) < CV_MIN_USABLE

    if siddetli or cv_zayif:
        sebep = []
        if siddetli:
            sebep.append(f"overfit={ml.get('overfit_verdict')}")
        if cv_zayif:
            sebep.append(f"CV dogruluk %{float(cv) * 100:.1f} < %{CV_MIN_USABLE * 100:.0f}")
        return M_OVERFIT_FAIL, True, "Model guvensiz: " + ", ".join(sebep)
    return 1.0, False, None


def classify_fund(fundamental: dict | None) -> tuple[float, str, str | None]:
    """M_fund: bilanco sagligi. (carpan, status, sebep)

    FAIL sarti UCU BIRDEN ister: nakit yakiyor VE marj cok negatif VE
    gelir daraliyor. Tek basina negatif nakit erken asama Ar-Ge
    sirketlerinde normaldir — kombinasyon patolojiktir.
    """
    f = fundamental or {}
    ocf = f.get("operating_cashflow")
    margin = f.get("profit_margin_pct")
    rev_yoy = f.get("revenue_growth_pct")

    ocf_neg = ocf is not None and float(ocf) < 0
    margin_bad = margin is not None and float(margin) < NET_MARGIN_FAIL_PCT
    rev_down = rev_yoy is not None and float(rev_yoy) < 0

    if ocf_neg and margin_bad and rev_down:
        return (M_FUND_FAIL, "FAIL",
                f"Nakit yakiyor ({float(ocf) / 1e6:.1f}M$), net marj "
                f"%{float(margin):.0f}, gelir YoY %{float(rev_yoy):.0f}")
    return 1.0, "PASS", None


def cap_news_uplift(
    overlay_bonus: float,
    moonshot_bonus: float,
    base_score: float,
    *,
    fund_status: str,
    pr_only: bool,
) -> tuple[float, str | None]:
    """Zayif temel VEYA PR_ONLY iken haber/vizyon kaldiracini tavanla.

    LAES'te stratejik+moonshot net katkisi +28 idi ve taban skorun buyuk
    kismini tasiyordu. Temel FAIL iken bu kaldiracin taban skorun
    %40'indan fazlasini tasimasi, "anlati bilancoyu yener" demektir.
    """
    net = float(overlay_bonus or 0) + float(moonshot_bonus or 0)
    if net <= 0:
        return net, None                     # ceza/negatif bonus kirpilmaz
    if fund_status != "FAIL" and not pr_only:
        return net, None

    tavan = max(0.0, float(base_score) * HABER_KALDIRAC_TAVAN_ORANI)
    if net <= tavan:
        return net, None
    sebep = (f"Haber/vizyon kaldiraci +{net:.1f} → +{tavan:.1f} kirpildi "
             f"({'PR_ONLY' if pr_only else 'temel FAIL'}; taban skorun "
             f"max %{HABER_KALDIRAC_TAVAN_ORANI * 100:.0f}'i)")
    return tavan, sebep


def apply_gates(
    score_raw: float,
    *,
    technical: dict | None = None,
    ml_result: dict | None = None,
    fundamental: dict | None = None,
    overlay_bonus: float = 0.0,
    moonshot_bonus: float = 0.0,
    base_score: float | None = None,
    pr_only: bool = False,
    binding: bool = False,
) -> dict[str, Any]:
    """Score_raw'a carpimsal kapilari uygular.

    Donen sozluk API/panel icin hazir: score_raw, final_score, M_*,
    market_status, overfit_verdict, pr_only, binding, reasons[].
    """
    reasons: list[str] = []

    m_market, market_status, r1 = classify_market(technical)
    m_overfit, is_overfit, r2 = classify_overfit(ml_result)
    m_fund, fund_status, r3 = classify_fund(fundamental)
    for r in (r1, r2, r3):
        if r:
            reasons.append(r)

    # Haber kaldiraci tavani: score_raw'dan FAZLALIGI dus
    duzeltilmis_raw = float(score_raw)
    if base_score is not None:
        kirpilmis, r4 = cap_news_uplift(
            overlay_bonus, moonshot_bonus, base_score,
            fund_status=fund_status, pr_only=pr_only,
        )
        if r4:
            fazlalik = (float(overlay_bonus or 0) + float(moonshot_bonus or 0)) - kirpilmis
            duzeltilmis_raw = max(0.0, duzeltilmis_raw - fazlalik)
            reasons.append(r4)

    final = duzeltilmis_raw * m_market * m_overfit * m_fund
    final = round(max(0.0, min(100.0, final)), 1)

    return {
        "score_raw": round(float(score_raw), 1),
        "score_after_uplift_cap": round(duzeltilmis_raw, 1),
        "final_score": final,
        "M_market": m_market,
        "M_overfit": m_overfit,
        "M_fund": m_fund,
        "market_status": market_status,
        "fund_status": fund_status,
        "is_overfit": is_overfit,
        "overfit_verdict": (ml_result or {}).get("overfit_verdict"),
        "pr_only": bool(pr_only),
        "binding": bool(binding),
        "reasons": reasons,
    }
