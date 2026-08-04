"""CARPIMSAL VETO REGRESYONLARI (denetim 03.08.2026).

Her vakanin altinda GERCEK bir olcum var — uydurma senaryo yok:

  LAES : 02.08.2026 canli calistirma — additive 94.5 "KRITIK ALIM" + PUSH.
         Ayni pakette: prob_up=0.376/SAT, overfit_verdict="SIDDETLI OVERFIT
         (model guvensiz)", CV dogruluk %51.6, train/CV gap 0.42,
         fiyat 2.54 < SMA20 2.57 < SMA50 2.99, net marj -%187,
         isletme nakit akisi -31.3M$, 120 gunde rakiplere karsi -69pp.

  ATOM : 02.08.2026 canli calistirma — additive 82.2 "GUCLU AL".
         +30'un tamami TEK baslikdan: "Atomera (ATOM) Makes Progress Towards
         Adoption of MST by GAA Manufacturers". Kok neden:
         strategic_overlays.ATOM_FOUNDRY_INTEGRATION_PATTERNS icindeki
         CIPLAK `\\bGAA\\b` kalibi. Ayni donemde gelir YoY -%78,
         moonshot modulu -5 ("J-Curve kirildi").

Testler AGA CIKMAZ: tum girdiler sabit sozluklerdir.

Calistir: python test_funnel_dashboard.py
"""

from __future__ import annotations

import evidence_classify as ec
import score_gate as sg
from verdict_rules import allow_push, gated_verdict

# ---------------------------------------------------------------------------
# Olculmus fikstürler (02.08.2026 canli calistirmadan)
# ---------------------------------------------------------------------------

LAES_TECH = {"close": 2.539900064468384, "sma_20": 2.5729949712753295,
             "sma_50": 2.991597981452942}
LAES_ML = {"prob_up": 0.3757, "cv_mean_accuracy": 0.516,
           "overfitting_gap": 0.4226,
           "overfit_verdict": "SIDDETLI OVERFIT (model guvensiz)"}
LAES_FUND = {"operating_cashflow": -31_257_000.0, "profit_margin_pct": -187.34399,
             "revenue_growth_pct": -12.0}
LAES_RAW = 94.5
LAES_BASE = 66.5
LAES_OVERLAY = 8      # ham +23, rakip kiyasi -15 sonrasi
LAES_MOONSHOT = 20

ATOM_TECH = {"close": 5.394999980926514, "sma_20": 5.760750007629395,
             "sma_50": 7.556000022888184}
ATOM_ML = {"prob_up": 0.1204, "cv_mean_accuracy": 0.5211,
           "overfit_verdict": "SIDDETLI OVERFIT (model guvensiz)"}
ATOM_FUND = {"operating_cashflow": -14_696_000.0, "profit_margin_pct": 0.0,
             "revenue_growth_pct": -78.0}
ATOM_BASLIK = ("Atomera (ATOM) Makes Progress Towards Adoption of MST by "
               "GAA Manufacturers")
ATOM_RAW = 82.2
ATOM_BASE = 57.2


# ---------------------------------------------------------------------------
# a) LAES-tipi
# ---------------------------------------------------------------------------

def test_laes_kritik_alim_ve_push_engellenir():
    g = sg.apply_gates(
        LAES_RAW, technical=LAES_TECH, ml_result=LAES_ML, fundamental=LAES_FUND,
        overlay_bonus=LAES_OVERLAY, moonshot_bonus=LAES_MOONSHOT,
        base_score=LAES_BASE, pr_only=False,
    )
    v, sebep = gated_verdict(
        g["final_score"], market_status=g["market_status"],
        is_overfit=g["is_overfit"], fund_status=g["fund_status"],
        pr_only=g["pr_only"],
    )
    izin, red = allow_push(v, market_status=g["market_status"],
                           is_overfit=g["is_overfit"])

    assert g["market_status"] == "FAIL", g
    assert g["is_overfit"] is True, g
    assert g["fund_status"] == "FAIL", g
    assert g["final_score"] < LAES_RAW, g
    assert v not in ("KRITIK ALIM", "GUCLU AL"), f"hala push bandinda: {v}"
    assert izin is False, (v, red)

    print(f"OK  LAES: raw={g['score_raw']} → uplift_cap={g['score_after_uplift_cap']} "
          f"→ final={g['final_score']}")
    print(f"    M_market={g['M_market']} M_overfit={g['M_overfit']} M_fund={g['M_fund']}")
    print(f"    verdict={v}  allow_push={izin}  ({red})")
    for r in g["reasons"][:3]:
        print(f"    - {r}")


def test_laes_haber_kaldiraci_kirpilir():
    """Temel FAIL iken stratejik+moonshot, taban skorun %40'ini asamaz."""
    kirpilmis, sebep = sg.cap_news_uplift(
        LAES_OVERLAY, LAES_MOONSHOT, LAES_BASE,
        fund_status="FAIL", pr_only=False,
    )
    tavan = LAES_BASE * sg.HABER_KALDIRAC_TAVAN_ORANI
    assert kirpilmis <= tavan + 0.01, (kirpilmis, tavan)
    assert sebep is not None
    print(f"OK  LAES kaldirac: +{LAES_OVERLAY + LAES_MOONSHOT} → +{kirpilmis:.1f} "
          f"(tavan {tavan:.1f} = taban {LAES_BASE} x %{sg.HABER_KALDIRAC_TAVAN_ORANI * 100:.0f})")


# ---------------------------------------------------------------------------
# b) ATOM-tipi tek PR
# ---------------------------------------------------------------------------

def test_atom_tek_pr_pr_only_isaretlenir():
    ev = ec.classify_evidence(ATOM_BASLIK)
    assert ev["pr_only"] is True, ev
    assert ev["binding"] is False, ev
    print(f"OK  ATOM basligi PR_ONLY: {ev['hits']['intent']}")


def test_atom_foundry_uplift_kirpilir():
    """+30 FOUNDRY INTEGRATION tek PR ile alinamaz."""
    ev = ec.classify_evidence(ATOM_BASLIK)
    kirpilmis, uyari = ec.clip_uplift(30, ev)
    assert kirpilmis == ec.PR_ONLY_UPLIFT_CAP, kirpilmis
    assert uyari is not None
    print(f"OK  ATOM uplift: +30 → +{kirpilmis} ({ec.PR_ONLY_UPLIFT_CAP} tavan)")


def test_atom_kritik_alim_ve_push_yok():
    # Kirpilmis uplift ile yeniden skorla: 82.2 - (30-8) = 60.2 taban varsayimi
    raw_kirpik = ATOM_RAW - (30 - ec.PR_ONLY_UPLIFT_CAP)
    g = sg.apply_gates(
        raw_kirpik, technical=ATOM_TECH, ml_result=ATOM_ML,
        fundamental=ATOM_FUND, overlay_bonus=ec.PR_ONLY_UPLIFT_CAP,
        moonshot_bonus=-5, base_score=ATOM_BASE, pr_only=True,
    )
    v, _ = gated_verdict(
        g["final_score"], market_status=g["market_status"],
        is_overfit=g["is_overfit"], fund_status=g["fund_status"],
        pr_only=g["pr_only"],
    )
    izin, red = allow_push(v, market_status=g["market_status"],
                           is_overfit=g["is_overfit"])
    assert v != "KRITIK ALIM", v
    assert izin is False, (v, red)
    print(f"OK  ATOM: raw={ATOM_RAW} → kirpik={raw_kirpik:.1f} → final={g['final_score']} "
          f"verdict={v} allow_push={izin}")


def test_atom_overlay_fonksiyonu_kirpiyor():
    """Gercek overlay fonksiyonu (strategic_overlays) uzerinden uctan uca."""
    from strategic_overlays import atom_licensing_signal

    haberler = [{"title": ATOM_BASLIK, "summary": "", "ticker": "ATOM"}]
    r = atom_licensing_signal(haberler)
    assert r["pr_only"] is True, r
    assert r["overlay_bonus"] <= ec.PR_ONLY_UPLIFT_CAP, r
    assert r["details"]["exponential_mode"] is False, r["details"]
    print(f"OK  atom_licensing_signal: bonus={r['overlay_bonus']} "
          f"exp_mode={r['details']['exponential_mode']} pr_only={r['pr_only']}")


# ---------------------------------------------------------------------------
# c) Tam gecis — huni "her seyi reddet" makinesi DEGIL
# ---------------------------------------------------------------------------

def test_tam_gecis_hala_push_uretebilir():
    """Baglayici kanit + saglikli temel + trend + temiz model → PUSH mumkun."""
    tech = {"close": 120.0, "sma_20": 100.0, "sma_50": 90.0}
    ml = {"prob_up": 0.62, "cv_mean_accuracy": 0.61,
          "overfit_verdict": "KABUL EDILEBILIR"}
    fund = {"operating_cashflow": 45_000_000.0, "profit_margin_pct": 18.0,
            "revenue_growth_pct": 34.0}
    ev = ec.classify_evidence(
        "Signed a long-term agreement; backlog grew 180%. "
        "Capacity reservation through 2029."
    )
    assert ev["binding"] is True and ev["pr_only"] is False, ev

    g = sg.apply_gates(
        88.0, technical=tech, ml_result=ml, fundamental=fund,
        overlay_bonus=15, moonshot_bonus=10, base_score=63.0,
        pr_only=ev["pr_only"], binding=ev["binding"],
    )
    v, _ = gated_verdict(
        g["final_score"], market_status=g["market_status"],
        is_overfit=g["is_overfit"], fund_status=g["fund_status"],
        pr_only=g["pr_only"],
    )
    izin, red = allow_push(v, market_status=g["market_status"],
                           is_overfit=g["is_overfit"])

    assert g["M_market"] == 1.0 and g["M_overfit"] == 1.0 and g["M_fund"] == 1.0, g
    assert g["final_score"] == 88.0, g
    assert v in ("KRITIK ALIM", "GUCLU AL"), v
    assert izin is True, (v, red)
    print(f"OK  tam gecis: final={g['final_score']} verdict={v} allow_push={izin}")


# ---------------------------------------------------------------------------
# d) Overfit + guclu trend → yine push YOK
# ---------------------------------------------------------------------------

def test_overfit_guclu_trendde_bile_push_yok():
    tech = {"close": 200.0, "sma_20": 100.0, "sma_50": 90.0}   # trend cok guclu
    ml = {"prob_up": 0.95, "overfit_verdict": "SIDDETLI OVERFIT",
          "cv_mean_accuracy": 0.52}
    fund = {"operating_cashflow": 10_000_000.0, "profit_margin_pct": 12.0,
            "revenue_growth_pct": 20.0}
    g = sg.apply_gates(96.0, technical=tech, ml_result=ml, fundamental=fund)
    v, _ = gated_verdict(
        g["final_score"], market_status=g["market_status"],
        is_overfit=g["is_overfit"], fund_status=g["fund_status"],
    )
    izin, red = allow_push(v, market_status=g["market_status"],
                           is_overfit=g["is_overfit"])
    assert g["M_overfit"] == sg.M_OVERFIT_FAIL, g
    assert izin is False, (v, red)
    print(f"OK  overfit+guclu trend: prob_up=0.95 raw=96.0 → final={g['final_score']} "
          f"verdict={v} allow_push=False ({red})")


def test_turkce_overfit_yazimi_da_yakalanir():
    """'ŞİDDETLİ OVERFIT' (Turkce karakterli) de yakalanmali."""
    m, is_of, _ = sg.classify_overfit({"overfit_verdict": "ŞİDDETLİ OVERFIT"})
    assert is_of is True and m == sg.M_OVERFIT_FAIL
    print("OK  Turkce 'ŞİDDETLİ OVERFIT' yazimi yakalandi")


# ---------------------------------------------------------------------------
# Kapilar YALNIZCA asagi ceker — hicbiri yukari tasimaz
# ---------------------------------------------------------------------------

def test_kapilar_asla_yukari_cekmez():
    g_temiz = sg.apply_gates(
        50.0,
        technical={"close": 120.0, "sma_20": 100.0, "sma_50": 90.0},
        ml_result={"overfit_verdict": "OK", "cv_mean_accuracy": 0.62},
        fundamental={"operating_cashflow": 1e7, "profit_margin_pct": 10.0,
                     "revenue_growth_pct": 5.0},
    )
    assert g_temiz["final_score"] == 50.0, g_temiz
    assert all(g_temiz[k] == 1.0 for k in ("M_market", "M_overfit", "M_fund"))
    print("OK  temiz paket carpanlari 1.0 — kapi yukari cekmiyor")


def test_veri_yoksa_ceza_yok():
    """Teknik/ML/temel verisi yoksa carpan 1.0 — 'bilinmiyor' != 'kotu'."""
    g = sg.apply_gates(70.0)
    assert g["final_score"] == 70.0, g
    assert g["market_status"] == "UNKNOWN", g
    print("OK  veri yoksa ceza uygulanmiyor (M=1.0, status=UNKNOWN)")


if __name__ == "__main__":
    print("=" * 76)
    print("  QUANT-DASHBOARD CARPIMSAL VETO — olculen deliklerin regresyonu")
    print("=" * 76 + "\n")

    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    bad = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as e:
            bad += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:
            bad += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
        print()

    print("=" * 76)
    print(f"  {len(fns) - bad}/{len(fns)} test gecti")
    print("=" * 76)
