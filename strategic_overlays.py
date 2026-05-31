"""
strategic_overlays.py - Hisse-spesifik 'Stratejik Beklenti' katmani.

Domain bilgisini koda dokmek:
  - IONQ + RGTI: bagimli kuantum sepeti ('All or Nothing')
  - ATOM:       IP Licensing modeli ('Royalty per Wafer')
  - LAES:       SEALSQ Corp - Post-Quantum Hardware Security (PQC + NIST)

Her hisse icin haber akisini tarar, kritik pattern eslesmelerinde
Master Score'a +/- katki uretir. Cikti formatı standartlasmistir:

  {
    "ticker": ...,
    "overlay_bonus": int,         # Master'a eklenir (-30..+40 araliginda)
    "labels": [str, ...],         # UI'da gosterilecek rozetler
    "details": {...},             # serbest dict
    "warnings": [str, ...],       # negatif uyarilar
    "evidence": [{title,link}, ...],
  }
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# =============================================================================
# 1) IONQ + RGTI - Kuantum Sepeti ('All or Nothing')
# =============================================================================

# 'Teknolojik Geçiş' tetikleyicileri (+25 puan)
QUANTUM_TRANSITION_PATTERNS = [
    r"\bFPGA[- ]based\s+quantum\s+control\b",
    r"\breal[- ]time\s+error\s+correction\b",
    r"\berror\s+correction\s+(integration|integrated|with)\s+(FPGA|GPU|classical)",
    r"\blogical\s+qubit(s)?\s+(achieved|demonstrated|operational)",
    r"\bfault[- ]tolerant\s+quantum\b",
    r"\bquantum\s+advantage\s+(demonstrated|achieved|proven)\b",
]

# 'Data Center Readiness' (+15 puan - oda sicakligi/uretim hazirligi)
DATACENTER_PATTERNS = [
    r"\broom[- ]temperature\s+(operation|qubit|quantum)\b",
    r"\bdata\s+center\s+(ready|deployment|integration)\b",
    r"\bcryogenic[- ]free\b",
    r"\benterprise[- ]grade\s+quantum\b",
    r"\bphotonic\s+integration\b",
]

# 'Standartlasma Tehdidi' (büyük teknoloji devleri standardize eder -> -15)
GIANT_STANDARDIZATION_PATTERNS = [
    r"\b(IBM|Google|Microsoft|AWS|Amazon)\s+(announce|set|drive|impose).*?(standard|API|protocol)",
    r"\bquantum\s+(industry|API)\s+standard\b",
    r"\b(IBM|Google)\s+open[- ]source\s+quantum\b",
    r"\bquantum\s+ecosystem\s+lock[- ]in\b",
]

# 'Teknolojik Sıçrama' (AQ artisi - bireysel hisse bonusu) +20
QUANTUM_LEAP_PATTERNS = [
    r"\bAQ\s*(64|72|96|128|256)\b",
    r"\balgorithmic\s+qubit(s)?\s+(reach|increase|expand)",
    r"\bqubit\s+count\s+(double|triple|increase)",
    r"\bnew\s+world\s+record\s+quantum\b",
    r"\bcoherence\s+time\s+(record|breakthrough|improve)",
]


def _match_count(text: str, patterns: list[str]) -> int:
    cnt = 0
    t = text.lower()
    for p in patterns:
        if re.search(p, t, re.IGNORECASE):
            cnt += 1
    return cnt


def _aggregate(news_items: list[dict]) -> str:
    return "\n".join((it.get("title", "") + " " + it.get("summary", ""))
                       for it in (news_items or []))


def quantum_basket_signal(ticker: str,
                            ticker_news: list[dict],
                            sibling_news: list[dict] | None = None,
                            ) -> dict:
    """
    IONQ/RGTI icin sepet analizi.

    ticker_news    -> bu hissenin haberleri
    sibling_news   -> sepetin diger uyesinin haberleri (IONQ icin RGTI ya da tersi)

    Logic:
      - Teknolojik gecis pattern eslesmesi: +25
      - Data center hazirligi: +15
      - Bireysel teknolojik sicrama (AQ artisi): +20
      - Standartlasma tehdidi: -15
      - Sibling hisse bullish -> 'sepet rüzgari' +5
    """
    bonus = 0
    labels: list[str] = []
    warnings: list[str] = []
    details = {}
    evidence: list[dict] = []

    text_self = _aggregate(ticker_news)
    text_sib = _aggregate(sibling_news or [])
    combined = text_self + "\n" + text_sib

    # 1) Teknolojik gecis (FPGA + GPU integration, real-time error correction)
    n_trans = _match_count(text_self, QUANTUM_TRANSITION_PATTERNS)
    n_trans_sib = _match_count(text_sib, QUANTUM_TRANSITION_PATTERNS)
    if n_trans > 0 or n_trans_sib > 0:
        # Sektor genel - bireysel hisseye yarisi yansisin
        bonus += 25 if n_trans > 0 else 12
        labels.append("🧬 TEKNOLOJIK GECIS (+25)")
        details["error_correction_fpga_hits"] = n_trans
        details["sibling_transition_hits"] = n_trans_sib

    # 2) Data Center Readiness (room temperature, photonic, enterprise-grade)
    n_dc = _match_count(text_self, DATACENTER_PATTERNS)
    if n_dc > 0:
        bonus += 15
        labels.append("🏢 DATA CENTER READY (+15)")
        details["datacenter_readiness_hits"] = n_dc

    # 3) Teknolojik Sıçrama (AQ artisi)
    n_leap = _match_count(text_self, QUANTUM_LEAP_PATTERNS)
    if n_leap > 0:
        bonus += 20
        labels.append("🚀 TEKNOLOJIK SICRAMA (+20)")
        details["leap_hits"] = n_leap

    # 4) Standartlasma Tehdidi
    n_std = _match_count(combined, GIANT_STANDARDIZATION_PATTERNS)
    if n_std > 0:
        bonus -= 15
        labels.append("⚠️ STANDARTLASMA TEHDIDI (-15)")
        warnings.append(
            f"IBM/Google/MS gibi devler kuantum standartlarini sekilliyor "
            f"({n_std} haber). Pure-play kuantum hisseleri marjinalize "
            f"olabilir.")
        details["standardization_threat_hits"] = n_std

    # 5) Sepet (sibling) rüzgari - klasik mean-reversion mantigi
    if sibling_news:
        sib_bull = _match_count(text_sib, QUANTUM_LEAP_PATTERNS +
                                  QUANTUM_TRANSITION_PATTERNS)
        if sib_bull >= 2:
            bonus += 5
            labels.append("🤝 SEPET RUZGARI (+5)")
            details["sibling_bullish_hits"] = sib_bull

    # Evidence (en ust 5 eslesen haber)
    for it in (ticker_news or [])[:8]:
        text = it.get("title", "") + " " + it.get("summary", "")
        for pat_set, tag in [
            (QUANTUM_TRANSITION_PATTERNS, "TRANSITION"),
            (DATACENTER_PATTERNS, "DATACENTER"),
            (QUANTUM_LEAP_PATTERNS, "LEAP"),
            (GIANT_STANDARDIZATION_PATTERNS, "THREAT"),
        ]:
            if any(re.search(p, text, re.IGNORECASE) for p in pat_set):
                evidence.append({
                    "tag": tag,
                    "title": it.get("title", "")[:160],
                    "link": it.get("link", ""),
                })
                break
        if len(evidence) >= 5:
            break

    return {
        "ticker": ticker,
        "overlay_type": "QUANTUM_BASKET",
        "overlay_bonus": bonus,
        "labels": labels,
        "warnings": warnings,
        "details": details,
        "evidence": evidence,
    }


# =============================================================================
# 2) ATOM - Atomera IP Licensing ('Royalty & Licensing' modeli)
# =============================================================================

# 'JDA / Standard Process Flow' - Foundry kabulu -> 10y EXPONENTIAL mod
ATOM_FOUNDRY_INTEGRATION_PATTERNS = [
    r"\bJDA\b",
    r"\bjoint\s+development\s+agreement\b",
    r"\bintegration\s+into\s+(standard\s+process\s+flow|production\s+line)",
    r"\bmst\s+(qualified|certified|approved)\s+for\s+production\b",
    r"\bproduction\s+(qualified|release|qualification)\b",
    r"\b(intel|tsmc|samsung|globalfoundries|umc)\s+(adopt|license|integrate)\s+MST",
    # GAA (Gate-All-Around) - 2nm/3nm sonrasi transistor mimarisi.
    # ATOMera GAA uretici ile evaluation/qualification asamasi.
    r"\bGAA\b",
    r"\bgate[- ]all[- ]around\b",
    r"\b(evaluation|qualification)\s+phase\s+with\s+(\w+\s+){0,3}(GAA|transistor|foundry|maker)",
    r"\b(ATOM|ATOMera|MST)\s+(enter\w*|move\w*|advanc\w*)\s+(into\s+)?evaluation\s+phase",
    r"\b(GAA|gate[- ]all[- ]around)\s+(transistor|maker|manufacturer|foundry)\s+(evaluat|qualif|adopt|integrat)",
    # Reverse phrasing: "moved into evaluation phase with one of the leading GAA"
    r"\b(into\s+)?evaluation\s+phase\s+with\s+(one\s+of\s+the\s+)?(leading\s+)?(GAA|gate[- ]all[- ]around)",
]

# 'Design Win / Royalty' - revenue-driving anlasmalar
ATOM_DESIGN_WIN_PATTERNS = [
    r"\bdesign\s+win\b",
    r"\broyalty\s+(per\s+wafer|agreement|deal|stream)",
    r"\blicensing\s+(deal|agreement|signed)",
    r"\bcommercial\s+license\b",
    r"\brevenue\s+sharing\b",
    r"\bIP\s+(transfer|deal|sale)\b",
]

# Performans / Verim kazanimi - teknolojik ustünlük
ATOM_PERFORMANCE_PATTERNS = [
    r"\b(\d+)\s*%\s+(performance|speed|efficiency)\s+(improve|increase|gain)",
    r"\b(\d+)\s*%\s+power\s+(reduction|reduce|save)",
    r"\bMobility\s+(improvement|enhance|boost)",
    r"\btransistor\s+(performance|efficiency)\s+(improve|enhance)",
    r"\bdrive\s+current\s+(increase|improve|boost)",
    r"\bband\s+engineering\b",
]

# Negatif: gecikme, partner cekilmesi
ATOM_NEGATIVE_PATTERNS = [
    r"\b(JDA|partnership)\s+(terminated|end|cancel|withdraw)",
    r"\blicensing\s+deal\s+(delay|stall)",
    r"\bfoundry\s+(reject|decline|pass\s+on)",
    r"\bdilut(ion|ive)\s+(offering|raise|secondary)",
]


def atom_licensing_signal(ticker_news: list[dict]) -> dict:
    """
    ATOM icin IP Licensing modeli analizi.

    Cikti:
      - overlay_bonus: -25..+40
      - exponential_mode: True ise 10y CAGR projeksiyonu daha agresif
      - design_wins: int
      - perf_gain_max_pct: int  (haberden cikari %25 gibi rakam)
    """
    bonus = 0
    labels = []
    warnings = []
    details = {
        "exponential_mode": False,
        "foundry_integration": False,
        "design_wins": 0,
        "performance_pct": [],
    }
    evidence = []

    text = _aggregate(ticker_news)

    # 1) Foundry Integration (production line kabulu) -> +30 + EXPONENTIAL mod
    n_int = _match_count(text, ATOM_FOUNDRY_INTEGRATION_PATTERNS)
    if n_int > 0:
        bonus += 30
        labels.append("🏭 FOUNDRY INTEGRATION (+30 + EXP MODE)")
        details["foundry_integration"] = True
        details["exponential_mode"] = True
        details["integration_hits"] = n_int

    # 2) Design Win / Royalty
    n_dw = _match_count(text, ATOM_DESIGN_WIN_PATTERNS)
    if n_dw > 0:
        bonus += min(15, n_dw * 5)
        labels.append(f"📜 DESIGN WIN x{n_dw} (+{min(15, n_dw * 5)})")
        details["design_wins"] = n_dw

    # 3) Performance gains - haberden % rakami cek
    perf_matches = re.findall(
        r"(\d+)\s*%\s+(?:performance|speed|efficiency|power)",
        text, re.IGNORECASE)
    if perf_matches:
        perf_nums = [int(x) for x in perf_matches if 5 <= int(x) <= 80]
        details["performance_pct"] = perf_nums
        if perf_nums:
            avg = sum(perf_nums) / len(perf_nums)
            # Her %10 verimlilik kazanci = +3 puan (max +12)
            bonus += min(12, int(avg / 10 * 3))
            labels.append(f"⚡ TEKNOLOJIK USTUNLUK +%{avg:.0f} ortalama")

    # 4) Negatif - JDA cancel, dilutive offering
    n_neg = _match_count(text, ATOM_NEGATIVE_PATTERNS)
    if n_neg > 0:
        bonus -= 25
        labels.append("⚠️ NEGATIF LISANS HABERLERI (-25)")
        warnings.append(
            f"ATOM icin {n_neg} negatif sinyal: JDA iptali / "
            f"hisse seyrelmesi / foundry reddi.")
        details["negative_hits"] = n_neg

    # Evidence
    for it in (ticker_news or [])[:10]:
        text2 = it.get("title", "") + " " + it.get("summary", "")
        for pat_set, tag in [
            (ATOM_FOUNDRY_INTEGRATION_PATTERNS, "FOUNDRY_INT"),
            (ATOM_DESIGN_WIN_PATTERNS, "DESIGN_WIN"),
            (ATOM_NEGATIVE_PATTERNS, "NEGATIVE"),
        ]:
            if any(re.search(p, text2, re.IGNORECASE) for p in pat_set):
                evidence.append({
                    "tag": tag,
                    "title": it.get("title", "")[:160],
                    "link": it.get("link", ""),
                })
                break
        if len(evidence) >= 5:
            break

    return {
        "ticker": "ATOM",
        "overlay_type": "ATOM_LICENSING",
        "overlay_bonus": bonus,
        "labels": labels,
        "warnings": warnings,
        "details": details,
        "evidence": evidence,
    }


# =============================================================================
# 3) LAES (SEALSQ) - Post-Quantum Hardware Security
# =============================================================================
# YENIDEN TANIMLANDI: LAES sembolu artik SEALSQ Corp (Kuantum Guvenlik) icin
# kullanilir. Eski lazer/sandblasting odagi tamamen kaldirildi.
# Yeni odak: PQC (Post-Quantum Cryptography), Secure Element, RISC-V Security,
# IoT Security, VaultiTrust, Matter Protocol, NIST PQC standartlari.

# NIST PQC hardware entegrasyonu - +30 master bonus (kullanici talebi)
# SOMUT patternler: gercek entegrasyon/sertifikasyon haberlerine bagli.
# Sadece "post-quantum AI robotics" gibi pazarlamayi YAKALAMAZ.
SEALSQ_NIST_INTEGRATION = [
    # 1) Acik NIST onayi + PQC
    r"\bNIST\s+(approved|standardized|certified|finalized|selected)\s+(PQC|post[- ]quantum|algorithm|standard)",
    # 2) Spesifik PQC algoritma + hardware/chip/silicon
    r"\b(CRYSTALS[- ](Kyber|Dilithium)|SPHINCS\+|FALCON|ML[- ]KEM|ML[- ]DSA|SLH[- ]DSA)\s+(hardware|chip|integrat|silicon|ASIC|deployed)",
    # 3) SEALSQ + entegrasyon fiili + NIST/PQC/FIPS
    r"\bSEALSQ\s+(integrat|implement|embed|deploy|ship|launch|achiev|advanc)\w*\s+(\w+\s+){0,4}(NIST|PQC|post[- ]quantum|FIPS|Common\s+Criteria)",
    # 4) FIPS sertifikasyonu - 140-3/140-2/203/204/205 ve basvuru/process dahil
    r"\bFIPS\s+140[- ]?[123]?(\s+(certif|compliant|validat|submission|application|filing|approval|process|in[- ]process))?",
    r"\bFIPS\s+(203|204|205)\s+(certif|compliant|validat|submission|application|filing)",
    # 4b) NIST FIPS basvuru ifadeleri
    r"\bNIST\s+FIPS\s+(submission|application|filing|approval|process)",
    r"\b(submitted|filed|completed)\s+(to\s+)?NIST(\s+for)?\s+FIPS",
    # 5) Common Criteria / EAL / CC Lab Letter guvenlik sertifikasi
    r"\bCommon\s+Criteria\s+(Security\s+)?Certif",
    r"\bCC\s+Lab\s+Letter",
    r"\bEAL\s*[2-7]\+?(\s+(certif|target|achiev))?",
    # 5b) QVault / TPM secure module
    r"\bQVault\s+(TPM|secure|module|chip)",
    r"\bsecure\s+(TPM|trusted\s+platform\s+module)\s+(certif|integrat|launch)",
    # 6) "Add post-quantum X to <somut cihaz>" - somut entegrasyon haberi
    #    (Parrot/drone, IoT cihaz, otomobil vb. somut hedef gerekli)
    r"\b(add|adding|added|deploy\w*|implement\w*|embed\w*)\s+post[- ]quantum\s+(cryptography|crypto|security|encryption)\s+to\s+(chip|silicon|drone|car|vehicle|IoT|device|robot|satellite|product|module)",
    # 7) Hardware/silicon-level PQC
    r"\b(hardware|silicon)[- ]level\s+(PQC|post[- ]quantum|quantum[- ]safe)",
    # 8) Spesifik SEALSQ urun adi + certif (QS7001, QS2 vb.)
    r"\bQS\d{3,4}\s+(secure\s+element|chip|certif|integrat)",
]

# Secure Element / IoT Design Wins - gercek partnership/customer haberleri
SEALSQ_DESIGN_WIN = [
    r"\bsecure\s+element\s+(design\s+win|adopt|select|integrat)",
    r"\bIoT\s+(device|chip|controller)\s+(secure|certif|design\s+win)",
    r"\bMatter\s+(protocol|certification|alliance)\s+(adopt|certif|integrat)",
    r"\bVaulti[Tt]rust\s+(deploy|integrat|partnership|customer)",
    r"\bRISC[- ]V\s+(security|trusted|secure)\s+(core|enclave|extension)",
    r"\bWISeKey\s+(deploy|partnership|customer)",
    # Spesifik partner/customer announcement (Parrot, Airbus vb. somut isimler)
    r"\bSEALSQ\s+(and|with)\s+\w+\s+(expand|sign|announce|launch)\s+(partnership|deal|contract|agreement)",
    r"\b(expand|sign|announce)\s+partnership\s+(with\s+)?SEALSQ",
]

# Kuantum tehdit / Q-Day talep patlamasi (10y catalyst)
SEALSQ_QDAY_PATTERNS = [
    r"\b[Qq][- ]day\s+(approach|imminent|preparing|threat|risk)",
    r"\bquantum\s+(threat|attack|crack|break)\s+(RSA|ECC|encryption)",
    r"\b(harvest\s+now,?\s+decrypt\s+later|HNDL)\b",
    r"\bcryptograph(y|ic)\s+(migration|transition|upgrade)\s+(plan|mandate)",
    r"\b(CNSA|NSM[- ]10|NSA)\s+(quantum|post[- ]quantum|migration)",
    r"\b(EU|US|UK|Germany|government)\s+(mandate|require)\s+(PQC|quantum[- ]safe)",
]

# Sektorel buyume motoru - IoT/Cybersecurity CAPEX
SEALSQ_CAPEX_DRIVERS = [
    r"\bIoT\s+(device|shipment|deployment)\s+(grow|increase|expand|record)",
    r"\bcybersecurity\s+(spending|CAPEX|budget|investment)\s+(grow|increase|expand)",
    r"\bglobal\s+(IoT|connected\s+device)\s+market\s+(grow|expand)",
    r"\b(IDC|Gartner|Forrester)\s+(report|forecast)\s+.*?(IoT|cybersecurity|PQC)",
    r"\bedge\s+(computing|AI)\s+(secure|trusted|certif)",
]

# Negatif sinyaller (PQC bekleme, gecikme, FIPS reject)
SEALSQ_NEGATIVE_PATTERNS = [
    r"\bFIPS\s+(reject|fail|denied|withdrawn)",
    r"\bPQC\s+(delay|postpone|behind)",
    r"\b(SEALSQ|WISeKey)\s+(delay|miss|setback|lawsuit)",
    r"\bquantum[- ]safe\s+(standard|migration)\s+(delay|push|postpone)",
    r"\bRSA\s+(remains|continue)\s+(safe|secure|standard)",  # kuantum tehdit zayifsa
]


def sealsq_pqc_signal(ticker_news: list[dict]) -> dict:
    """
    LAES (=SEALSQ Corp) icin Post-Quantum Hardware Security sinyali.

    KADEMELI BONUSLAR (gercek haber kalitesine duyarli kalibrasyon):
      NIST PQC hw integration  -> 1hit:+15 / 2hit:+22 / 3+hit:+30
      Secure Element design win -> +8 per hit, max +20
      Q-Day demand spike        -> 1hit:+5 / 2+hit:+10
      IoT/Cybersec CAPEX        -> +3 per hit, max +8
      Negatif (FIPS reject)     -> -25
    Net teorik max ~ +73 (gerceki haberlerle nadiren +30'u gecer)
    Master Score'da ayrica strategic clamp ±40 var.
    """
    bonus = 0
    labels = []
    warnings = []
    details = {
        "nist_integration": False,
        "design_wins": 0,
        "qday_signals": 0,
        "capex_driver_signals": 0,
        "demand_spike_active": False,
    }
    evidence = []

    text = _aggregate(ticker_news)

    # 1) NIST PQC hardware entegrasyonu - KADEMELI
    n_nist = _match_count(text, SEALSQ_NIST_INTEGRATION)
    if n_nist >= 3:
        nist_b = 30
    elif n_nist == 2:
        nist_b = 22
    elif n_nist == 1:
        nist_b = 15
    else:
        nist_b = 0
    if nist_b > 0:
        bonus += nist_b
        details["nist_integration"] = (n_nist >= 2)  # tam onay icin >=2 hit
        labels.append(f"🔐 NIST PQC ENTEGRASYONU (+{nist_b}) [{n_nist} hit]")

    # 2) Secure Element / IoT Design Win (+8 her, max +20)
    n_dw = _match_count(text, SEALSQ_DESIGN_WIN)
    if n_dw > 0:
        dw_bonus = min(20, n_dw * 8)
        bonus += dw_bonus
        details["design_wins"] = n_dw
        labels.append(f"🛡️ SECURE ELEMENT DESIGN WIN (+{dw_bonus}) [{n_dw} hit]")

    # 3) Q-Day Demand Spike (kademeli, max +10)
    n_qday = _match_count(text, SEALSQ_QDAY_PATTERNS)
    if n_qday >= 2:
        qd_b = 10
    elif n_qday == 1:
        qd_b = 5
    else:
        qd_b = 0
    if qd_b > 0:
        bonus += qd_b
        details["qday_signals"] = n_qday
        details["demand_spike_active"] = (n_qday >= 2)
        labels.append(f"⚡ Q-DAY DEMAND SPIKE (+{qd_b}) [{n_qday} hit]")
        if n_qday >= 2:
            warnings.append(
                "Q-Day yaklasimi: Kuantum bilgisayarlar RSA/ECC kirma "
                "esigine yaklasiyor. SEALSQ icin TALEP PATLAMASI katalisti.")

    # 4) IoT / Cybersecurity CAPEX ruzgari (+3 per, max +8)
    n_capex = _match_count(text, SEALSQ_CAPEX_DRIVERS)
    if n_capex > 0:
        cap_bonus = min(8, n_capex * 3)
        bonus += cap_bonus
        details["capex_driver_signals"] = n_capex
        labels.append(f"📈 IoT / CYBERSEC CAPEX RUZGARI (+{cap_bonus})")

    # 5) Negatif sinyaller
    n_neg = _match_count(text, SEALSQ_NEGATIVE_PATTERNS)
    if n_neg > 0:
        neg = -min(25, n_neg * 8)
        bonus += neg
        labels.append(f"⚠️ NEGATIF PQC SINYAL ({neg})")
        warnings.append("FIPS sertifika veya PQC roadmap gecikme isareti.")

    # Evidence
    for it in (ticker_news or [])[:15]:
        text2 = (it.get("title", "") + " " + it.get("summary", "")).lower()
        for pat_set, tag in [
            (SEALSQ_NIST_INTEGRATION, "NIST_PQC"),
            (SEALSQ_DESIGN_WIN,       "DESIGN_WIN"),
            (SEALSQ_QDAY_PATTERNS,    "Q_DAY"),
            (SEALSQ_CAPEX_DRIVERS,    "CAPEX_DRIVER"),
            (SEALSQ_NEGATIVE_PATTERNS,"NEGATIVE"),
        ]:
            if any(re.search(p, text2, re.IGNORECASE) for p in pat_set):
                evidence.append({
                    "tag": tag,
                    "title": it.get("title", "")[:160],
                    "link": it.get("link", ""),
                })
                break
        if len(evidence) >= 6:
            break

    return {
        "ticker": "LAES",
        "company": "SEALSQ Corp",
        "overlay_type": "SEALSQ_PQC",
        "overlay_bonus": bonus,
        "labels": labels,
        "warnings": warnings,
        "details": details,
        "evidence": evidence,
    }


# Geri uyumluluk: eski isim import edilirse calismaya devam etsin
def laes_industrial_signal(ticker_news: list[dict],
                              heavy_industry_news=None) -> dict:
    """Deprecated - LAES artik SEALSQ. sealsq_pqc_signal'a yonlendirir."""
    return sealsq_pqc_signal(ticker_news)


# =============================================================================
# 4) NVTS - GaN power semi (Moonshot adayi)
# =============================================================================
# Kullanici talebi:
#   - NVDA yeni veri merkezi guc gereksinimi haberi -> NVTS'e +15 master
#   - Tier-1 OEM (Tesla/VW/Hyundai) tedarik anlasmasi -> kritik esik

# AI / Hyperscaler data center guc gereksinimi haberleri (NVDA tarafindan)
NVTS_DC_POWER_PATTERNS = [
    # NVDA cipi + rack/datacenter + power (genis kalibrasyon, "rack-scale" tek kelime varyant)
    r"\b(NVIDIA|NVDA)\s+(GB\d+|Blackwell|Rubin|Vera|H\d+|B\d+)\s+(\w+\s+){0,3}(power|cooling|watt|kW|MW|consumption)",
    r"\b(NVIDIA|NVDA)\s+(\w+\s+){0,2}(rack[- ]?scale|hyperscale|datacenter|data\s+center)",
    r"\b(rack[- ]?scale|hyperscale)\s+(GPU|AI|datacenter|data\s+center)\s+(power|kW|MW|consumption)",
    r"\b(rack[- ]?scale)\s+\d+(\.\d+)?\s*(MW|kW)\s+power",   # "rack-scale 1.2MW power"
    r"\b48V\s+(rack|GPU|AI|data\s*center|server)\s+(power|supply|architecture|conversion)",
    r"\bAI\s+(server|data\s*center|cluster)\s+power\s+(grow|increase|demand|consumption|surge)",
    r"\bdata\s+center\s+(power|electricity)\s+(demand|consumption)\s+(grow|double|triple|surge)",
    r"\b(800V|HVDC)\s+(data\s*center|AI|hyperscale)",
]

# Tier-1 OEM (Tesla/VW/Hyundai/Stellantis/Ford/GM) tedarik anlasmasi - kritik esik
NVTS_TIER1_AUTO_PATTERNS = [
    r"\b(Tesla|Volkswagen|VW|Hyundai|Kia|Stellantis|Ford|GM|BMW|Mercedes|Toyota|Honda|Rivian|Lucid)\s+(\w+\s+){0,4}(NVTS|Navitas|GaN|GaNFast|GaNSense)",
    r"\bNavitas\s+(\w+\s+){0,4}(Tier[- ]?1|OEM|automotive|EV|vehicle)\s+(\w+\s+){0,2}(supply|contract|deal|win|partnership|adopt)",
    r"\bGaN(Fast|Sense)?\s+(\w+\s+){0,3}(automotive|EV|vehicle|traction|inverter|on[- ]board\s+charger|OBC)",
    r"\b(automotive\s+grade|AEC[- ]Q1?0[01])\s+(GaN|Navitas|NVTS)",
    r"\b(traction\s+inverter|on[- ]board\s+charger|DC[- ]DC\s+converter)\s+(\w+\s+){0,3}(Navitas|NVTS|GaN)",
]


def navitas_gan_signal(ticker_news: list[dict],
                          nvda_news: list[dict] | None = None) -> dict:
    """
    NVTS (Navitas) icin AI DC + Tier-1 OEM sinyali.

    Bonuslar (kullanici talebi):
      AI Data Center Power (NVDA tarafından)  -> +15 master
      Tier-1 Auto OEM Tedarik Anlasmasi       -> +20 master (kritik esik)
      Hem haber + somut OEM ismi varsa        -> +5 kombo
      EV verim yuzdesi (>%20)                 -> +5
    """
    bonus = 0
    labels = []
    warnings = []
    details = {
        "dc_power_news": 0,
        "tier1_auto_news": 0,
        "tier1_oems": [],
        "dc_power_active": False,
        "tier1_threshold_crossed": False,
    }
    evidence = []

    text = _aggregate(ticker_news)
    nvda_text = _aggregate(nvda_news or [])

    # 1) NVDA tarafından AI DC guc haberi (NVTS'e ruzgar)
    n_dc_nvda = _match_count(nvda_text, NVTS_DC_POWER_PATTERNS)
    n_dc_self = _match_count(text, NVTS_DC_POWER_PATTERNS)
    n_dc = n_dc_nvda + n_dc_self
    if n_dc > 0:
        bonus += 15
        details["dc_power_news"] = n_dc
        details["dc_power_active"] = True
        src = ("NVDA tarafindan" if n_dc_nvda > 0 else "NVTS haberinden")
        labels.append(f"🖥️ AI DC POWER SINYALI (+15) [{src} - {n_dc} hit]")

    # 2) Tier-1 OEM tedarik anlasmasi (kritik esik)
    n_t1 = _match_count(text, NVTS_TIER1_AUTO_PATTERNS)
    if n_t1 > 0:
        bonus += 20
        details["tier1_auto_news"] = n_t1
        details["tier1_threshold_crossed"] = True
        labels.append(f"🚗 TIER-1 OEM TEDARIK (+20 KRITIK ESIK) [{n_t1} hit]")
        # Hangi OEM'ler isimlerini cek
        oem_re = r"\b(Tesla|Volkswagen|VW|Hyundai|Kia|Stellantis|Ford|GM|BMW|Mercedes|Toyota|Honda|Rivian|Lucid)\b"
        for m in re.finditer(oem_re, text, re.IGNORECASE):
            name = m.group(0)
            if name not in details["tier1_oems"]:
                details["tier1_oems"].append(name)

    # 3) DC + Tier-1 kombo bonusu (her ikisi de varsa stratejik)
    if n_dc > 0 and n_t1 > 0:
        bonus += 5
        labels.append("⚡ DC + TIER-1 KOMBO (+5)")

    # 4) Verim yuzdesi (>%20) - GaN avantaji
    eff_matches = re.findall(
        r"(\d+)\s*%\s+(efficien|loss\s+reduction|power\s+density)",
        text, re.IGNORECASE)
    if eff_matches:
        try:
            nums = [int(x) for x, _ in eff_matches if 5 <= int(x) <= 80]
            if nums and max(nums) >= 20:
                bonus += 5
                labels.append(f"⚡ Yuksek verim haberi ({max(nums)}%)")
        except Exception:
            pass

    # Evidence
    for it in (ticker_news or [])[:12]:
        text2 = (it.get("title", "") + " " + it.get("summary", "")).lower()
        for pat_set, tag in [
            (NVTS_DC_POWER_PATTERNS,    "DC_POWER"),
            (NVTS_TIER1_AUTO_PATTERNS,  "TIER1_OEM"),
        ]:
            if any(re.search(p, text2, re.IGNORECASE) for p in pat_set):
                evidence.append({
                    "tag": tag,
                    "title": it.get("title", "")[:160],
                    "link": it.get("link", ""),
                })
                break
        if len(evidence) >= 5:
            break

    return {
        "ticker": "NVTS",
        "company": "Navitas Semiconductor",
        "overlay_type": "NVTS_GAN",
        "overlay_bonus": bonus,
        "labels": labels,
        "warnings": warnings,
        "details": details,
        "evidence": evidence,
    }


# =============================================================================
# Dispatcher: ticker -> uygun overlay
# =============================================================================
def get_overlay(ticker: str, news_items: list[dict] | None,
                  sibling_news: list[dict] | None = None,
                  heavy_industry_news: list[dict] | None = None,
                  nvda_news: list[dict] | None = None) -> dict:
    """
    Hisse bazli stratejik overlay'i tetikle.

    Args:
      ticker: hisse sembolu
      news_items: bu hissenin haberleri
      sibling_news: IONQ icin RGTI, RGTI icin IONQ
      heavy_industry_news: LAES icin otomotiv/heavy industry haberleri
      nvda_news: NVTS icin NVDA DC power haberleri
    """
    if news_items is None:
        news_items = []

    ticker_u = ticker.upper()
    if ticker_u in ("IONQ", "RGTI", "QBTS"):
        return quantum_basket_signal(ticker_u, news_items, sibling_news)
    if ticker_u == "ATOM":
        # Ticker'i evidence icin items'a ekle
        for it in news_items:
            it.setdefault("ticker", "ATOM")
        return atom_licensing_signal(news_items)
    if ticker_u == "LAES":
        # LAES sembolu = SEALSQ Corp (Post-Quantum Hardware Security)
        return sealsq_pqc_signal(news_items)
    if ticker_u == "NVTS":
        # Navitas GaN - AI DC + Tier-1 OEM kritik esikleri
        return navitas_gan_signal(news_items, nvda_news)

    # Diger hisseler icin no-op
    return {
        "ticker": ticker_u,
        "overlay_type": "NONE",
        "overlay_bonus": 0,
        "labels": [],
        "warnings": [],
        "details": {},
        "evidence": [],
    }


# Hangi hisseler 'speculative' (yuksek risk) bayragiyla isaretlenir
SPECULATIVE_TICKERS = {
    "IONQ", "RGTI", "QBTS", "QUBT", "ATOM", "LAES",
    "CRDO", "ALAB", "POET", "ARQQ", "AMBA",
}


def is_speculative(ticker: str) -> bool:
    return ticker.upper() in SPECULATIVE_TICKERS
