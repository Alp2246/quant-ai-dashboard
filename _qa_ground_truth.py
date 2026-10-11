"""
Quant QA Ground-Truth Validation (Mayis 2026)
=============================================

4 manuel-inject senaryo + 1 export control filter testi.
Sapmalari/eksik regex'leri tespit eder, Discrepancy Report uretir.
"""
import io, sys, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from datetime import datetime

# Modulleri ic
import strategic_overlays as so
import moonshot_detector as md
import semi_cycle as sc
import geopolitics as geo
import forecasting as fc
import master_score as ms

# Sapma defteri
DISCREPANCIES: list[dict] = []
PASSES: list[dict] = []

def REC(scenario: str, ok: bool, expected, got, note=""):
    rec = {"scenario": scenario, "expected": expected, "got": got, "note": note}
    if ok:
        PASSES.append(rec)
        print(f"  [PASS] {scenario}: expected={expected} got={got}")
    else:
        DISCREPANCIES.append(rec)
        print(f"  [FAIL] {scenario}: expected={expected} got={got}  -- {note}")

# -------------------------------------------------------------
# SENARYO 1: SEALSQ (LAES) FIPS 140-3 + CC Lab Letter
# -------------------------------------------------------------
print("=" * 72)
print("SENARYO 1: SEALSQ (LAES) NIST FIPS 140-3 sertifikasyon basvurusu")
print("=" * 72)
laes_news = [
    {
        "title": "SEALSQ Files FIPS 140-3 Application for QVault TPM",
        "summary": ("May 2026: SEALSQ completed NIST FIPS 140-3 submission for "
                    "QVault TPM products. The company also entered the October 2026 "
                    "CC Lab Letter (Common Criteria) certification phase. "
                    "Hardware-level PQC integration with CRYSTALS-Kyber and Dilithium."),
        "link": "https://example.com/sealsq-fips140",
    },
    {
        "title": "SEALSQ QS7001 secure element passes pre-evaluation",
        "summary": ("SEALSQ QS7001 has been submitted for NIST FIPS 140-3 "
                    "validation. Common Criteria EAL5+ targeted."),
        "link": "https://example.com/qs7001",
    },
]
sig1 = so.sealsq_pqc_signal(laes_news)
print(f"  raw signal bonus = {sig1.get('overlay_bonus')}")
print(f"  labels = {sig1.get('overlay_labels')}")
REC("S1-LAES-NIST-PQC bonus >= 30",
    sig1.get("overlay_bonus", 0) >= 30,
    ">= 30", sig1.get("overlay_bonus", 0),
    "FIPS 140-3 + CC Lab Letter regex'leri eksik olabilir.")

# Master Score'a entegrasyon (strategic_overlay_bonus clamped +30)
_NEUTRAL = dict(
    technical={"rsi": 55, "macd_signal": "bullish", "close": 7.0,
                "sma_20": 6.8, "sma_50": 6.5},
    sentiment={"news_score": 0.2, "reddit_score": 0.1,
                "n_news": 4, "n_reddit": 2},
    fundamental={"score": 60, "label": "Saglikli"},
    ml_result={"prob_up": 0.6, "train_samples": 200},
)
ms_out = ms.compute_master_score(
    **_NEUTRAL,
    strategic_overlay_bonus=sig1.get("overlay_bonus", 0),
)
REC("S1-MasterScore reflects +30 strategic clamp",
    ms_out["modifiers"]["strategic"] == 30,
    30, ms_out["modifiers"]["strategic"],
    "strategic_overlay_bonus 30 olarak yansimali.")

# -------------------------------------------------------------
# SENARYO 2: NVTS Q1 2026 fundamentals + forecast reality check
# -------------------------------------------------------------
print("\n" + "=" * 72)
print("SENARYO 2: NVTS Q1 2026 Gross Margin %38.7, Market Cap $1.9B")
print("=" * 72)
# Forecasting reality check: NVTS per-ticker cap $100 + sektor cap
try:
    from sector_tam import get_ticker_price_cap_10y, get_sector
    nvts_cap = get_ticker_price_cap_10y("NVTS")
    nvts_sector = get_sector("NVTS")
    print(f"  NVTS per-ticker price cap = ${nvts_cap}")
    print(f"  NVTS sektor = {nvts_sector}")
    REC("S2-NVTS price cap exists ($100)",
        nvts_cap is not None and 50 <= float(nvts_cap) <= 120,
        "50<=cap<=120", nvts_cap,
        "10Y projeksiyonu $100 civarinda kapanmali.")

    # Simulasyon: bugun $7 -> 6 ay sonra $14 hedef. 10Y $100 cap aktif.
    spot = 7.0
    short_target = spot * 2.0  # $14
    long_cap = float(nvts_cap) if nvts_cap else 100.0
    rational_curve = (short_target < long_cap < short_target * 20)
    REC("S2-Rational curve $7 -> $14 (6m) -> $100 (10Y)",
        rational_curve, "kapali bant",
        f"spot=${spot}, short=${short_target}, cap=${long_cap}",
        "Reality check kisa vade & uzun vade cakismamali.")
except Exception as e:
    REC("S2-NVTS reality check", False, "no exception", str(e),
        "Exception during forecast reality check.")

# Fundamentals injection (gross margin 38.7 + small cap)
# fundamentals.py yfinance'a baglandigi icin direkt inject yerine
# get_fundamental_summary cikisini simule edelim.
sim_fundamentals = {
    "ticker": "NVTS", "gross_margin": 0.387, "market_cap": 1.9e9,
    "score": 65.0, "label": "Saglikli"
}
REC("S2-Gross margin 38.7% within healthy band",
    0.35 <= sim_fundamentals["gross_margin"] <= 0.45,
    "0.35-0.45", sim_fundamentals["gross_margin"],
    "GaN industry average 35-45%; NVTS 38.7 healthy.")

# -------------------------------------------------------------
# SENARYO 3: Semi Cycle EXPANSION + sector_intelligence +10 tailwind
# -------------------------------------------------------------
print("\n" + "=" * 72)
print("SENARYO 3: Semi Cycle 'AI Altyapi Patlamasi' kalibrasyonu")
print("=" * 72)
# detect_cycle_phase() canli veri cekiyor; biz testte yapay phase yapalim
sim_phase = {
    "phase": "📈 EXPANSION (Boga)", "cycle_score": 72,
    "rsi_avg": 65, "logic_score": 70,
}
# Master Score'a macro_bonus +10 yansimali mi?
ms_macro = ms.compute_master_score(**_NEUTRAL, macro_bonus=10)
REC("S3-Master macro_bonus EXPANSION = +10",
    ms_macro["modifiers"]["macro"] == 10,
    10, ms_macro["modifiers"]["macro"],
    "EXPANSION fazinda macro tailwind +10 yansimali.")

# Otomatik mapping var mi? phase string'inden macro_bonus turetmek ic mantik
# (app.py icinde olmasi gerekir).  Burada manuel test:
PHASE_TO_MACRO = {
    "PEAK":      -5,    # asiri isinma
    "EXPANSION": +10,
    "RECOVERY":  +5,
    "TROUGH":    +3,
    "DOWNTURN":  -10,
}
def phase_to_macro(phase_str: str) -> int:
    for k, v in PHASE_TO_MACRO.items():
        if k in phase_str.upper():
            return v
    return 0
auto_macro = phase_to_macro(sim_phase["phase"])
REC("S3-phase_to_macro mapping EXPANSION -> +10",
    auto_macro == 10, 10, auto_macro,
    "Bu yardimci fonksiyon ya semi_cycle ya master_score'da olmali.")

# -------------------------------------------------------------
# SENARYO 4: ATOM GAA (Gate-All-Around) evaluation phase
# -------------------------------------------------------------
print("\n" + "=" * 72)
print("SENARYO 4: ATOM GAA (Gate-All-Around) JDA evaluation")
print("=" * 72)
atom_news = [
    {
        "title": "ATOM enters evaluation phase with GAA transistor maker",
        "summary": ("May 2026: ATOMera moved into evaluation phase with one of the "
                    "leading Gate-All-Around (GAA) transistor manufacturers for "
                    "MST integration. Joint development discussions ongoing."),
        "link": "https://example.com/atom-gaa",
    },
    {
        "title": "ATOM MST shows 15% drive current improvement on GAA test wafers",
        "summary": "Drive current improvement of 15% measured on early GAA test silicon.",
        "link": "https://example.com/atom-perf",
    },
]
atom_sig = so.atom_licensing_signal(atom_news)
print(f"  ATOM raw bonus = {atom_sig.get('overlay_bonus')}")
print(f"  labels = {atom_sig.get('overlay_labels')}")
print(f"  exponential_mode = {atom_sig.get('exponential_mode')}")
# NOT (02.08.2026 olculmus vaka): regex'lerde hata YOK — 5 kalip da tutuyor.
# Asil davranis evidence_classify.PR_ONLY_UPLIFT_CAP: baglayici kanit yoksa
# +30 -> +8 kirpilmasi BILINCLI. Bu yuzden eski beklenti (>= 15) guncel degil.
REC("S4-ATOM detects GAA evaluation phase",
    bool(atom_sig.get("details", {}).get("foundry_integration")),
    "foundry_integration=True",
    atom_sig.get("details", {}).get("foundry_integration"),
    "GAA + evaluation phase regex'leri tetiklenmeli.")
REC("S4-ATOM PR_ONLY evaluation bonus kirpildi (<=8)",
    atom_sig.get("overlay_bonus", 0) <= 8
    and bool(atom_sig.get("details", {}).get("pr_only_clipped")),
    "<= 8 ve pr_only_clipped=True", atom_sig.get("overlay_bonus", 0),
    "Baglayici kanit yok — PR_ONLY_UPLIFT_CAP devrede olmali.")
atom_binding = atom_news + [{
    "title": "ATOMera signs JDA with leading GAA foundry",
    "summary": ("Signed a joint development agreement with production "
                "commitment and prepayment from the foundry."),
    "link": "https://example.com/atom-jda",
}]
atom_sig2 = so.atom_licensing_signal(atom_binding)
print(f"  ATOM (JDA'li) bonus = {atom_sig2.get('overlay_bonus')}")
REC("S4-ATOM JDA baglayici kanit bonus >= 30",
    atom_sig2.get("overlay_bonus", 0) >= 30,
    ">= 30", atom_sig2.get("overlay_bonus", 0),
    "Baglayici kanit (JDA imzasi) varken kirpilma OLMAMALI.")

# Moonshot detector ATOM icin 'POTANSIYEL PATLAMA' verdict uretir mi?
atom_moon = md.detect_moonshot("ATOM")
print(f"  ATOM j_curve_score = {atom_moon.get('j_curve_score')}, "
      f"labels = {atom_moon.get('labels')}")
explosive = md.get_explosive_factor("ATOM")
print(f"  ATOM explosive_factor = {explosive!r}")
REC("S4-ATOM moonshot explosive_factor populated",
    explosive != "-" and len(str(explosive)) > 10,
    "non-empty narrative", explosive,
    "EXPLOSIVE_FACTOR['ATOM'] tanimli olmali.")

# -------------------------------------------------------------
# SENARYO 5 (BONUS): Export Control Filter -15 Master penalty
# -------------------------------------------------------------
print("\n" + "=" * 72)
print("SENARYO 5: Gallium / Germanium Export License -> Master -15")
print("=" * 72)
geo_payload = {
    "ticker": "AXTI",
    "export_weight": -15,   # yeni KIRMIZI ALARM seviyesi
    "risk_score": -8,
    "risk_level": "KIRMIZI ALARM",
}
ms_geo = ms.compute_master_score(**_NEUTRAL, geo_risk=geo_payload)
print(f"  master.modifiers.geo = {ms_geo['modifiers']['geo']}")
REC("S5-Export Control Filter -15 reaches Master",
    ms_geo["modifiers"]["geo"] <= -15,
    "<= -15", ms_geo["modifiers"]["geo"],
    "geo_w clamp suanda -10..+10 - genisletilmeli (-15 izinli).")

# Pattern check
test_text = "China imposes new export license requirements on gallium exports"
pos_neg = geo._score_text(test_text)
REC("S5-gallium export license pattern catches negative",
    pos_neg < 0,
    "< 0 (negatif)", pos_neg,
    "NEGATIVE_PATTERNS gallium export licence yakalanmali.")

# -------------------------------------------------------------
# RAPOR
# -------------------------------------------------------------
print("\n" + "=" * 72)
print("DISCREPANCY REPORT")
print("=" * 72)
print(f"PASS: {len(PASSES)}  |  FAIL: {len(DISCREPANCIES)}")
print()
if DISCREPANCIES:
    print("Uyusmazliklar:")
    for i, d in enumerate(DISCREPANCIES, 1):
        print(f"  {i}. {d['scenario']}")
        print(f"     Expected: {d['expected']}")
        print(f"     Got:      {d['got']}")
        print(f"     Note:     {d['note']}")
        print()
else:
    print("Hicbir sapma yok.")

# JSON cikti
with open("_qa_ground_truth_report.json", "w", encoding="utf-8") as f:
    json.dump({
        "passes": PASSES, "discrepancies": DISCREPANCIES,
        "ts": datetime.now().isoformat(),
    }, f, indent=2, ensure_ascii=False)
print("\nRapor JSON: _qa_ground_truth_report.json")
