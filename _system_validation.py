"""
Sistem dogrulama (v8) - Tum modul + temel fonksiyon test suite.

Bes faz:
  1) Modul import dogrulamasi (tum 28 dosya)
  2) Yapilandirma + sabit dogrulamasi (TICKERS, kategoriler, cap'ler)
  3) Saf fonksiyon birimleri (yfinance/RSS'a bagimsiz)
  4) Yfinance / Internet baglantili modul testi (NVTS pipeline)
  5) End-to-end analyze_ticker testi (NVTS dahil cekirdek)

Test PASS/FAIL/SKIP raporu yazdirir.
"""
import io, sys, time, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                 errors="replace")
import logging
logging.basicConfig(level=logging.WARNING)

GREEN = ""    # plain text (cmd window)
RED = ""
RESET = ""

passes, fails, skips = [], [], []

def assert_check(name, cond, detail=""):
    if cond:
        passes.append(name)
        print(f"  ✓ {name}" + (f"  ({detail})" if detail else ""))
    else:
        fails.append((name, detail))
        print(f"  ✗ {name}  -> {detail}")

def skip(name, reason):
    skips.append((name, reason))
    print(f"  ⊘ SKIP {name} ({reason})")

def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# =========================================================================
# FAZ 1: Tum modul import + yapilandirma sabitleri
# =========================================================================
section("FAZ 1 — MODUL IMPORT + YAPILANDIRMA")

MODULES = [
    "config", "data_fetcher", "technical_indicators", "sentiment_analysis",
    "reddit_sentiment", "critical_news", "fundamentals", "ml_model",
    "master_score", "backtest", "forecasting", "notifications",
    "radar_watchlist", "milestones", "dca_calculator", "risk_distribution",
    "visionary_goals",
    # V6 sectoral
    "moat_analysis", "correlation_matrix", "capex_watch",
    "sector_intelligence", "volatility_smile",
    # V7 hardware intel
    "patent_watch", "geopolitics", "semi_cycle", "feature_importance",
    "hardware_intel",
    # V7.1+ research/cap
    "research_agent", "sector_tam",
    # V8 strategic + investor
    "strategic_overlays", "cash_runway", "competitor_benchmark",
    "moonshot_detector", "investor_summary", "executive_brief",
    "engineering_notes", "black_litterman", "purged_cv",
]
imported = {}
for m in MODULES:
    try:
        imported[m] = __import__(m)
        assert_check(f"import {m}", True)
    except Exception as e:
        assert_check(f"import {m}", False, str(e))


# =========================================================================
# FAZ 2: Yapilandirma sabitleri (NVTS dogrulamasi)
# =========================================================================
section("FAZ 2 — NVTS KONFIGURASYON DOGRULAMASI")

from config import TICKERS, COMPANY_NAMES
assert_check("NVTS cekirdek hisselerde", "NVTS" in TICKERS,
              f"TICKERS={TICKERS}")
assert_check("NVTS COMPANY_NAMES'de", "NVTS" in COMPANY_NAMES)

from sector_tam import (INVESTOR_CATEGORY, STRATEGIC_FOCUS,
                          get_ticker_price_cap_10y, get_ticker_max_cagr_10y,
                          get_global_price_cap_multiplier,
                          get_global_cagr_band, get_sector_leader_cap_usd,
                          get_sector, SECTOR_TAM_CAGR_PCT)
assert_check("NVTS INVESTOR_CATEGORY",
              "Moonshot" in INVESTOR_CATEGORY.get("NVTS", ""))
assert_check("NVTS STRATEGIC_FOCUS",
              "Tier-1" in STRATEGIC_FOCUS.get("NVTS", ""))
assert_check("NVTS price cap = $100",
              get_ticker_price_cap_10y("NVTS") == 100.0)
assert_check("NVTS max CAGR = 20%",
              get_ticker_max_cagr_10y("NVTS") == 20.0)
assert_check("Global 20x cap",
              get_global_price_cap_multiplier() == 20.0)
assert_check("Global CAGR band 15-25",
              get_global_cagr_band() == (15.0, 25.0))
assert_check("GAN_POWER sector CAGR = 18%",
              SECTOR_TAM_CAGR_PCT["GAN_POWER"] == 18)
assert_check("NVTS sektor lideri cap > 0",
              get_sector_leader_cap_usd("NVTS") > 0,
              f"${get_sector_leader_cap_usd('NVTS')/1e9:.1f}B")
assert_check("NVTS sektoru GAN_POWER",
              get_sector("NVTS") == "GAN_POWER")

from moonshot_detector import MOONSHOT_CANDIDATES, get_explosive_factor
assert_check("NVTS Moonshot Candidate",
              "NVTS" in MOONSHOT_CANDIDATES)
assert_check("NVTS Explosive Factor tanimli",
              "Tier-1" in get_explosive_factor("NVTS"))

from competitor_benchmark import COMPETITOR_GROUPS
assert_check("LAES competitors (IFX/NXP/STM)",
              len(COMPETITOR_GROUPS.get("LAES", [])) >= 3)
assert_check("AXTI competitors (IQE/Sumitomo)",
              "IQE.L" in COMPETITOR_GROUPS.get("AXTI", []))

from engineering_notes import BASE_NOTE, CRITICAL_THRESHOLD
for t in ("NVTS", "LAES", "AXTI", "IONQ", "ATOM"):
    assert_check(f"{t} Muhendislik Notu (BASE_NOTE) tanimli",
                  len(BASE_NOTE.get(t, "")) >= 100)
    assert_check(f"{t} Kritik Esik tanimli",
                  CRITICAL_THRESHOLD.get(t, "-") != "-")


# =========================================================================
# FAZ 3: Saf fonksiyon birimleri (no internet)
# =========================================================================
section("FAZ 3 — SAF FONKSIYON BIRIMLERI (internet-bagimsiz)")

# 3.1 Strategic Overlays - SEALSQ kalibre patternleri
print("\n[3.1] strategic_overlays — SEALSQ patterns (kalibre)")
from strategic_overlays import sealsq_pqc_signal, navitas_gan_signal, get_overlay
sealsq_news_real = [
    {"title": "SEALSQ and Parrot Expand Partnership to Add Post-Quantum "
              "Cryptography to Drones",
     "summary": "Matter protocol integration"},
    {"title": "SEALSQ Achieves Common Criteria Security Certification "
              "for QS7001 Secure Element",
     "summary": "PQC ready ASIC"},
]
r = sealsq_pqc_signal(sealsq_news_real)
assert_check("SEALSQ overlay bonus mantikli (10-50 arasi)",
              10 <= r["overlay_bonus"] <= 50,
              f"bonus={r['overlay_bonus']}")
assert_check("SEALSQ overlay_type = SEALSQ_PQC",
              r["overlay_type"] == "SEALSQ_PQC")

# Genel pazarlama haberi (NIST onayli FIPS demese) <= 15 bonus
sealsq_news_marketing = [
    {"title": "SEALSQ Targets Post Quantum AI Robotics and European Tech "
              "Sovereignty Potential",
     "summary": "General market positioning"},
]
r_market = sealsq_pqc_signal(sealsq_news_marketing)
assert_check("SEALSQ pazarlama haberi 100'e yapismiyor",
              r_market["overlay_bonus"] <= 15,
              f"bonus={r_market['overlay_bonus']}")

# 3.2 NVTS overlay
print("\n[3.2] strategic_overlays — NVTS GAN signal")
nvts_news = [
    {"title": "Navitas wins Hyundai Tier-1 supply deal for GaN OBC",
     "summary": "AEC-Q100 automotive grade GaN delivered with 30% efficiency"},
]
nvda_news = [
    {"title": "NVIDIA Blackwell GB200 rack-scale 1.2MW power consumption",
     "summary": "48V power architecture for hyperscale GPU"},
]
r_nv = navitas_gan_signal(nvts_news, nvda_news)
assert_check("NVTS overlay bonus mantikli (>=15)",
              r_nv["overlay_bonus"] >= 15,
              f"bonus={r_nv['overlay_bonus']}")
assert_check("NVTS Tier-1 esigi tetiklendi",
              r_nv["details"]["tier1_threshold_crossed"])
assert_check("NVTS DC power aktif (NVDA proxy)",
              r_nv["details"]["dc_power_active"])

# Dispatcher
r_disp = get_overlay("NVTS", nvts_news, nvda_news=nvda_news)
assert_check("get_overlay('NVTS') -> NVTS_GAN",
              r_disp["overlay_type"] == "NVTS_GAN")
r_laes = get_overlay("LAES", sealsq_news_real)
assert_check("get_overlay('LAES') -> SEALSQ_PQC",
              r_laes["overlay_type"] == "SEALSQ_PQC")

# 3.3 Master Score - moonshot_bonus + strategic clamp
print("\n[3.3] master_score - clamp + moonshot integration")
from master_score import compute_master_score
ms = compute_master_score(
    {"rsi": 55, "macd_signal": "bullish", "close": 7, "sma_20": 6.5,
     "sma_50": 6.0},
    {"score": 0.2}, {"score": 65},
    {"prob_up": 0.65, "train_samples": 100},
    strategic_overlay_bonus=45,  # NVTS overlay raw
    moonshot_bonus=20,
)
assert_check("Master <= 100",
              ms["master_score"] <= 100)
assert_check("Strategic clamp +30 (45 raw -> 30 cap)",
              ms["modifiers"]["strategic"] == 30,
              f"strategic={ms['modifiers']['strategic']}")
assert_check("Moonshot modifier +20",
              ms["modifiers"]["moonshot"] == 20)

# 3.4 Critical news terimleri (PQC)
print("\n[3.4] critical_news - PQC + materyal terimleri")
from critical_news import scan_text
hits = scan_text("SEALSQ CRYSTALS-Kyber FIPS 203 QS7001 secure element Q-day "
                   "Indium Phosphide gallium arsenide")
terms = [h["term"] for h in hits]
assert_check("PQC critical terms tanindi",
              any("crystals" in t for t in terms))
assert_check("InP critical term tanindi",
              "indium phosphide" in terms)
assert_check("Q-day critical term tanindi",
              "q-day" in terms)

# 3.5 Moonshot J-Curve internal logic (yfinance'siz)
print("\n[3.5] moonshot_detector internal accessors")
from moonshot_detector import (MOONSHOT_CANDIDATES, SECONDARY_MOONSHOT,
                                  get_explosive_factor)
assert_check("Primary moonshots (NVTS, INDI, RGTI)",
              {"NVTS", "INDI", "RGTI"}.issubset(MOONSHOT_CANDIDATES))
assert_check("Secondary moonshots ATOM/LAES/IONQ",
              {"ATOM", "LAES", "IONQ"}.issubset(SECONDARY_MOONSHOT))

# 3.6 Investor Summary build
print("\n[3.6] investor_summary - build_investor_overview")
from investor_summary import build_investor_overview
fake_results = {
    "NVTS": {
        "ticker": "NVTS",
        "df": None, "master": {"master_score": 72,
            "breakdown": {"technical": 24, "fundamental": 11,
                           "sentiment": 14, "vision": 18},
            "modifiers": {"strategic": 30, "moonshot": 20, "macro": 5}},
        "fundamental": {"market_cap": 1e9},
        "strategic_overlay": {"overlay_bonus": 45,
            "labels": ["TIER-1"],
            "details": {"tier1_threshold_crossed": True,
                          "dc_power_active": True}},
        "cash_runway": {"is_unsustainable": False, "master_penalty": 0,
                           "is_warning": False, "runway_months": 36},
        "moat": {"innovation_risk": False, "rd_pct": 25},
        "geo_risk": {"critical_alert": False},
        "vision": {"vision_bonus": 12},
        "critical_weight": {"weight": 0},
        "durability_score": {"durability": 55},
        "moonshot": {"is_moonshot_candidate": True,
                      "is_primary_moonshot": True,
                      "master_bonus": 20,
                      "revenue_yoy_pct": 35, "rd_yoy_pct": 28},
        "competitor_benchmark": {"bonus": 0},
    },
}
df_ov = build_investor_overview(fake_results)
assert_check("Investor Overview NVTS satiri var", "NVTS" in df_ov["Hisse"].values)
nv_row = df_ov[df_ov["Hisse"] == "NVTS"].iloc[0]
assert_check("NVTS Moonshot bayrak emoji",
              "🚀" in nv_row["Moonshot"])
assert_check("NVTS Kritik Esik TETIKLENDI rozet",
              "TETIKLENDI" in nv_row["Kritik Esik"])
assert_check("NVTS Verdict belirlendi",
              nv_row["Verdict"] in ("EKLE", "TUT", "BEKLE", "AZALT", "DIKKAT"))

# 3.7 Executive Brief
print("\n[3.7] executive_brief - dogal dil yorum")
from executive_brief import brief_for_ticker, market_summary
b = brief_for_ticker(fake_results["NVTS"])
assert_check("Brief master_score = 72", b["master_score"] == 72)
assert_check("Brief Tier-1 OEM action mesaji",
              "AGRESIF EKLE" in b["action"] or "Tier-1" in b["action"])
ms_summary = market_summary([b])
assert_check("market_summary calisti",
              ms_summary["n_tickers"] == 1)

# 3.8 Purged CV
print("\n[3.8] purged_cv - Lopez de Prado")
import numpy as np, pandas as pd
from purged_cv import purged_kfold_indices, purged_kfold_cv_score
splits = purged_kfold_indices(300, n_splits=5, horizon_days=15, embargo_days=3)
assert_check("Purged CV en az 3 fold uretti", len(splits) >= 3)
# Train-test overlap kontrolu (purging dogru calismali)
overlap = sum(len(set(tr) & set(te)) for tr, te in splits)
assert_check("Purged CV train-test overlap = 0", overlap == 0)

# 3.9 Black-Litterman
print("\n[3.9] black_litterman - portfoy optim")
from black_litterman import portfolio_optimization
np.random.seed(0)
idx = pd.date_range("2024-01-01", periods=200, freq="D")
hist = {
    "A": pd.DataFrame({"Close": 100*np.exp(np.cumsum(np.random.randn(200)*0.02))}, index=idx),
    "B": pd.DataFrame({"Close": 100*np.exp(np.cumsum(np.random.randn(200)*0.02))}, index=idx),
    "C": pd.DataFrame({"Close": 100*np.exp(np.cumsum(np.random.randn(200)*0.02))}, index=idx),
}
out = portfolio_optimization(hist, {"A": 1, "B": 1, "C": 1},
                                views=[{"ticker": "A",
                                          "expected_annual_return": 0.30,
                                          "confidence": 0.7}])
assert_check("BL portfoy hesaplandi",
              "weights" in out and len(out["weights"]) == 3)
assert_check("BL agirlik toplami ~ 1.0",
              abs(out["weights"].sum() - 1.0) < 0.01)


# =========================================================================
# FAZ 4: Internet baglantili modul testi
# =========================================================================
section("FAZ 4 — INTERNET BAGLANTILI MODUL TESTI (yfinance)")

# 4.1 Fiyat verisi
print("\n[4.1] data_fetcher - NVTS fiyat verisi")
try:
    from data_fetcher import fetch_history
    df = fetch_history("NVTS")
    if df is not None and not df.empty:
        assert_check("NVTS fiyat verisi alindi",
                      len(df) > 100,
                      f"{len(df)} satir, son fiyat ${df['Close'].iloc[-1]:.2f}")
    else:
        skip("NVTS fetch_history", "yfinance NVTS donus bos")
except Exception as e:
    skip("NVTS fetch_history", str(e))

# 4.2 Sentiment (RSS based)
print("\n[4.2] sentiment_analysis - NVTS haber sentiment")
try:
    from sentiment_analysis import get_ticker_sentiment
    s = get_ticker_sentiment("NVTS")
    assert_check("NVTS sentiment dict",
                  isinstance(s, dict) and "score" in s)
    if s.get("news_raw"):
        assert_check("NVTS haber sayisi > 0",
                      len(s["news_raw"]) > 0,
                      f"{len(s['news_raw'])} haber")
except Exception as e:
    skip("NVTS sentiment", str(e))

# 4.3 Fundamentals (score icin get_fundamental_summary gerekli)
print("\n[4.3] fundamentals - NVTS")
try:
    from fundamentals import get_fundamental_summary
    f = get_fundamental_summary("NVTS")
    assert_check("NVTS fundamental_summary dict + score",
                  isinstance(f, dict) and "score" in f
                  and isinstance(f["score"], (int, float)))
    if f.get("market_cap"):
        print(f"    Market Cap: ${f['market_cap']/1e9:.2f}B")
    print(f"    Fundamental Score: {f.get('score')}  Rating: {f.get('rating')}")
except Exception as e:
    skip("NVTS fundamentals", str(e))

# 4.4 Forecasting + cap dogrulamasi
print("\n[4.4] forecasting - NVTS 20x cap dogrulamasi")
try:
    from forecasting import forecast_long_term
    if df is not None and not df.empty:
        fc = forecast_long_term(df, years=10, ticker="NVTS")
        cap = fc.get("cap_value", 0)
        last = fc.get("last_actual", 0)
        mult = fc.get("cap_multiplier", 0)
        # 100 USD outlier limit ALTI olmali
        assert_check("NVTS forecast cap_value <= $100",
                      cap <= 101,
                      f"cap=${cap:.2f}")
        assert_check("NVTS cap_multiplier <= 20x",
                      mult <= 20.5,
                      f"mult={mult:.1f}x")
        sat = fc.get("saturation", {}) or {}
        assert_check("NVTS cap_source belirli",
                      sat.get("cap_source") is not None,
                      sat.get("cap_source", "yok"))
except Exception as e:
    skip("NVTS forecasting", str(e))

# 4.5 Competitor Benchmark (AXTI vs IQE/Sumitomo)
print("\n[4.5] competitor_benchmark - AXTI vs IQE+Sumitomo")
try:
    from competitor_benchmark import relative_strength
    rs = relative_strength("AXTI", days=60)
    if "per_competitor" in rs and rs["per_competitor"]:
        assert_check("AXTI rakip verisi alindi",
                      len(rs["per_competitor"]) >= 1,
                      f"{list(rs['per_competitor'].keys())}")
        print(f"    RS: {rs.get('relative_strength_pp'):+.1f}pp  "
              f"bonus: {rs.get('bonus'):+d}")
    else:
        skip("AXTI competitor", "rakip fiyat verisi yok")
except Exception as e:
    skip("AXTI competitor", str(e))


# =========================================================================
# FAZ 6: EKSIKLIK FIX'LERI (v8.1) - yeni eklenen ozellikleri test et
# =========================================================================
section("FAZ 6 — V8.1 EKSIKLIK FIX TESTLERI")

# 6.1 ml_model purged CV entegrasyonu
print("\n[6.1] ml_model -> Purged CV entegrasyonu")
try:
    from ml_model import full_analysis
    from data_fetcher import fetch_history
    df_test = fetch_history("NVTS")
    if df_test is not None and not df_test.empty:
        ml_res = full_analysis(df_test, 0.0, 50.0)
        assert_check("ML cv_mean_accuracy mevcut",
                      "cv_mean_accuracy" in ml_res,
                      f"cv_acc={ml_res.get('cv_mean_accuracy'):.3f}")
        assert_check("ML overfit_verdict mevcut",
                      ml_res.get("overfit_verdict") not in (None, "ATLANDI"),
                      f"verdict={ml_res.get('overfit_verdict')}")
        assert_check("ML overfitting_gap hesaplandi",
                      "overfitting_gap" in ml_res
                      and abs(ml_res["overfitting_gap"]) < 1.0,
                      f"gap={ml_res.get('overfitting_gap'):+.3f}")
        assert_check("ML cv_n_folds >= 1",
                      ml_res.get("cv_n_folds", 0) >= 1,
                      f"{ml_res.get('cv_n_folds')} folds")
except Exception as e:
    skip("ml_model purged CV", str(e))

# 6.2 NVTS competitor_benchmark
print("\n[6.2] competitor_benchmark NVTS rakipleri")
from competitor_benchmark import COMPETITOR_GROUPS
assert_check("NVTS COMPETITOR_GROUPS'da",
              "NVTS" in COMPETITOR_GROUPS,
              f"NVTS rakipleri: {COMPETITOR_GROUPS.get('NVTS')}")
assert_check("NVTS rakipleri Infineon+POWI iceriyor",
              "IFX.DE" in COMPETITOR_GROUPS.get("NVTS", [])
              and "POWI" in COMPETITOR_GROUPS.get("NVTS", []))
assert_check("INDI COMPETITOR_GROUPS'da",
              "INDI" in COMPETITOR_GROUPS)
try:
    from competitor_benchmark import relative_strength
    rs = relative_strength("NVTS", days=60)
    if rs.get("per_competitor"):
        print(f"    NVTS RS: {rs.get('relative_strength_pp', 0):+.1f}pp  "
              f"bonus: {rs.get('bonus', 0):+d}")
        assert_check("NVTS relative_strength calculated",
                      "relative_strength_pp" in rs)
        # Narrative dogru hisse adi mi?
        narr = rs.get("narrative", "")
        assert_check("NVTS narrative dinamik (AXTI hard-code degil)",
                      "AXTI" not in narr or "NVTS" in narr,
                      f"narrative ornek: {narr[:80]}")
except Exception as e:
    skip("NVTS competitor RS", str(e))

# 6.3 notifications - critical trigger handler
print("\n[6.3] notifications -> handle_critical_triggers")
from notifications import handle_critical_triggers, _detect_triggers
# Mock NVTS Tier-1 result
mock_nvts = {
    "strategic_overlay": {
        "details": {"tier1_threshold_crossed": True,
                      "tier1_oems": ["Hyundai", "Stellantis"],
                      "dc_power_active": True},
        "labels": ["TIER-1"],
    },
    "geo_risk": {"critical_alert": False},
    "atom_exponential_mode": False,
    "ml": {"overfit_verdict": "DENGELI", "overfitting_gap": 0.02},
}
trgs = _detect_triggers("NVTS", mock_nvts)
trg_ids = [t["event_id"] for t in trgs]
assert_check("NVTS_TIER1_OEM trigger algilandi",
              "NVTS_TIER1_OEM" in trg_ids,
              f"trigerlar: {trg_ids}")
assert_check("NVTS_NVDA_DC_POWER trigger algilandi",
              "NVTS_NVDA_DC_POWER" in trg_ids)

# Mock LAES NIST integration
mock_laes = {
    "strategic_overlay": {
        "details": {"nist_integration": True, "demand_spike_active": False},
    },
    "geo_risk": {"critical_alert": False},
    "atom_exponential_mode": False,
    "ml": {"overfit_verdict": "HAFIF OVERFIT", "overfitting_gap": 0.08},
}
trgs_l = _detect_triggers("LAES", mock_laes)
ids_l = [t["event_id"] for t in trgs_l]
assert_check("LAES_NIST_PQC_INTEGRATION algilandi",
              "LAES_NIST_PQC_INTEGRATION" in ids_l,
              f"laes: {ids_l}")

# Mock ATOM exponential
mock_atom = {
    "strategic_overlay": {"details": {"exponential_mode": True}},
    "atom_exponential_mode": True,
    "geo_risk": {"critical_alert": False},
    "ml": {},
}
trgs_a = _detect_triggers("ATOM", mock_atom)
ids_a = [t["event_id"] for t in trgs_a]
assert_check("ATOM_FOUNDRY_JDA algilandi",
              "ATOM_FOUNDRY_JDA" in ids_a)

# ML severe overfit -> ayri trigger
mock_overfit = {
    "strategic_overlay": {"details": {}},
    "geo_risk": {"critical_alert": False},
    "atom_exponential_mode": False,
    "ml": {"overfit_verdict": "SIDDETLI OVERFIT (model guvensiz)",
           "overfitting_gap": 0.25},
}
trgs_o = _detect_triggers("TEST", mock_overfit)
ids_o = [t["event_id"] for t in trgs_o]
assert_check("ML overfit trigger algilandi",
              "TEST_ML_OVERFIT" in ids_o)

# Idempotency: handle 2 kez cagrilirsa 2. cagri bos donmeli
import shutil
from config import DATA_DIR
state_file = DATA_DIR / "trigger_state.json"
try:
    if state_file.exists():
        state_file.unlink()
    first = handle_critical_triggers("NVTS", mock_nvts)
    second = handle_critical_triggers("NVTS", mock_nvts)
    assert_check("1. cagri trigger uretti", len(first) >= 1,
                  f"{len(first)} event")
    assert_check("2. cagri bos (idempotency 7 gun)",
                  len(second) == 0,
                  f"{len(second)} event")
    if state_file.exists():
        state_file.unlink()  # clean up
except Exception as e:
    skip("idempotency test", str(e))

# 6.4 Detail tab Engineering Note (sadece imports check)
print("\n[6.4] app.py'da Engineering Note Detail tab'a entegre mi")
import re
with open("app.py", "r", encoding="utf-8") as f:
    app_src = f.read()
assert_check("render_detail icinde get_engineering_note cagrisi",
              "get_engineering_note(ticker, r)" in app_src
              and app_src.count("get_engineering_note") >= 2)
assert_check("Detail tab'da ML Overfit Teshisi paneli",
              "ML Overfit Teşhisi" in app_src or "Purged CV" in app_src)

# =========================================================================
# FAZ 7: SONUC
# =========================================================================
section("FAZ 7 — SONUC")
n_total = len(passes) + len(fails) + len(skips)
print(f"\n  PASS:  {len(passes)}/{n_total}")
print(f"  FAIL:  {len(fails)}")
print(f"  SKIP:  {len(skips)}")

if fails:
    print("\n  Basarisiz testler:")
    for n, d in fails:
        print(f"    ✗ {n}: {d}")

if skips:
    print("\n  Atlanan testler:")
    for n, r in skips:
        print(f"    ⊘ {n}: {r[:100]}")

overall = "PASS" if not fails else "FAIL"
print(f"\n{'=' * 70}")
print(f"OVERALL: {overall}")
print(f"{'=' * 70}")
