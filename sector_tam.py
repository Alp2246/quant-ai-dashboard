"""
sector_tam.py - Sektor Total Addressable Market (TAM) haritasi.

10 yillik fiyat projeksiyonlarinda 'akil sinirlari' icin kullanilir.
Eger bir hisse 10y sonra TAM'nin %50'sini geciyorsa otomatik revize edilir.

Veriler 2026 Q1 sektor raporlarinin makul tahminleridir (TrendForce, Gartner,
McKinsey, SEMI WSTS). Yillik 6-10% TAM buyume varsayar (10y horizon).

Tum rakamlar USD cinsinden milyar dolar.
"""
from __future__ import annotations


# Sektor TAM (Total Addressable Market) - 2026'da $bn cinsinden bugunku boyut
SECTOR_TAM_BN_USD = {
    "QUANTUM_COMPUTING": 8,       # 2026 boyutu cok kucuk, 2030 ~50, 2035 ~150
    "SIC_POWER":         15,      # SiC pazari, EV ile patliyor
    "GAN_POWER":         5,       # GaN pazari kucuk ama hizli buyuyor
    "EUV_LITHO":         32,      # ASML monopol, dar pazar
    "INP_GAAS":          12,      # Compound semi (AXTI, II-VI)
    "AUTO_SOC":          80,      # Automotive cipler (INDI, NXP, MBLY)
    "DUV_FOUNDRY":       180,     # Mature node foundries (SMIC, Hua Hong)
    "MST_LICENSING":     1.5,     # Atomera niche
    "SECURE_MCU":        7,       # SEALSQ, post-quantum HW
    "AI_ACCEL":          250,     # GPU + AI ASIC (NVDA dominates)
    "MEMORY":            170,     # DRAM + NAND
    "FOUNDRY_LEADING":   500,     # TSMC, Samsung leading nodes
    "AI_INTERCONNECT":   28,      # AEC, PCIe/CXL retimer, SiPho engine
    "SEMI_TEST_EQUIP":   9,       # Burn-in / wafer-level test (AEHR)
    "AI_DC_INFRA":       55,      # Rack power, liquid cooling (VRT, SMCI)
    "CUSTOM_ASIC":       120,     # Broadcom/Marvell hyperscaler XPU
    "EDGE_AI_FPGA":      14,      # Lattice low-power FPGA
    "CPU_IP":            35,      # Arm licensing
    "PQC_SOFTWARE":      6,       # Post-quantum SaaS (ARQQ)
    "AI_ENTERPRISE_SW":  45,      # Palantir-class enterprise AI
    "DEFAULT":           50,      # Tanimsiz sektor icin
}

# 10 yillik beklenen TAM bilesik buyumesi (CAGR%) - sektor bazli
SECTOR_TAM_CAGR_PCT = {
    "QUANTUM_COMPUTING": 35,
    "SIC_POWER":         22,
    "GAN_POWER":         18,    # NVTS sektor CAGR bandi %15-20 (kullanici talebi)
    "EUV_LITHO":         12,
    "INP_GAAS":          15,
    "AUTO_SOC":          11,
    "DUV_FOUNDRY":       6,
    "MST_LICENSING":     20,
    "SECURE_MCU":        22,   # Q-Day yaklasimi -> talep patlamasi 2027-2030
    "AI_ACCEL":          25,
    "MEMORY":            8,
    "FOUNDRY_LEADING":   10,
    "AI_INTERCONNECT":   26,
    "SEMI_TEST_EQUIP":   18,
    "AI_DC_INFRA":       20,
    "CUSTOM_ASIC":       22,
    "EDGE_AI_FPGA":      14,
    "CPU_IP":            16,
    "PQC_SOFTWARE":      32,
    "AI_ENTERPRISE_SW":  18,
    "DEFAULT":           10,
}

# Hisse -> sektor mapping
TICKER_TO_SECTOR = {
    "IONQ":      "QUANTUM_COMPUTING",
    "RGTI":      "QUANTUM_COMPUTING",
    "QUBT":      "QUANTUM_COMPUTING",
    "WOLF":      "SIC_POWER",
    "NVTS":      "GAN_POWER",
    "ASML":      "EUV_LITHO",
    "AXTI":      "INP_GAAS",
    "INDI":      "AUTO_SOC",
    "ATOM":      "MST_LICENSING",
    "LAES":      "SECURE_MCU",
    "NVDA":      "AI_ACCEL",
    "AMD":      "AI_ACCEL",
    "MU":       "MEMORY",
    "TSM":      "FOUNDRY_LEADING",
    "INTC":     "FOUNDRY_LEADING",
    "0981.HK":  "DUV_FOUNDRY",
    "1347.HK":  "DUV_FOUNDRY",
  # AI + Kuantum cagi genisletme
    "QBTS":     "QUANTUM_COMPUTING",
    "CRDO":     "AI_INTERCONNECT",
    "ALAB":     "AI_INTERCONNECT",
    "POET":     "AI_INTERCONNECT",
    "AEHR":     "SEMI_TEST_EQUIP",
    "AVGO":     "CUSTOM_ASIC",
    "MRVL":     "CUSTOM_ASIC",
    "VRT":      "AI_DC_INFRA",
    "SMCI":     "AI_DC_INFRA",
    "LSCC":     "EDGE_AI_FPGA",
    "ARM":      "CPU_IP",
    "ARQQ":     "PQC_SOFTWARE",
    "PLTR":     "AI_ENTERPRISE_SW",
    "AMBA":     "AUTO_SOC",
}


# Yatirimci sunumu icin sade kategori isimleri (kullanici talebi)
# v8 STRATEJIK ROL TANIMLAMALARI (kullanici talebi)
# Her hisse 5 ana kategoriden birine atanir:
#   Moonshot / Defense / Infrastructure / Royalty / Foundation
INVESTOR_CATEGORY = {
    "NVTS":     "Moonshot - GaN & SiC Power Revolution",
    "INDI":     "Moonshot - Autonomous SoC (L3+ FSD)",
    "IONQ":     "Moonshot - Quantum Computing Hardware (AQ 64+)",
    "RGTI":     "Moonshot - Superconducting Quantum Scale",
    "QUBT":     "Moonshot - Photonic Quantum Networking",
    "LAES":     "Defense - Post-Quantum Hardware Security",
    "ATOM":     "Royalty - Semiconductor IP Licensing (MST)",
    "AXTI":     "Infrastructure - Compound Semi Substrates (6G + Photonik)",
    "WOLF":     "Infrastructure - SiC Power (EV megacycle)",
    "ASML":     "Foundation - EUV Lithography Monopoly",
    "NVDA":     "Foundation - AI Accelerator (CUDA moat)",
    "0981.HK":  "Foundation - China DUV Foundry (SMIC)",
    "1347.HK":  "Foundation - China DUV Foundry (Hua Hong)",
    "QBTS":     "Moonshot - Quantum Annealing (D-Wave)",
    "CRDO":     "Moonshot - AI Active Electrical Cable (800G/1.6T)",
    "ALAB":     "Moonshot - PCIe/CXL Retimer (AI Rack Fabric)",
    "POET":     "Moonshot - Silicon Photonics Optical Engine",
    "AEHR":     "Royalty - SiC/GaN Test Equipment (Pickaxe)",
    "AVGO":     "Foundation - Custom AI ASIC (Hyperscaler XPU)",
    "MRVL":    "Foundation - Custom AI Silicon (Cloud/Edge)",
    "VRT":      "Infrastructure - AI Data Center Power & Cooling",
    "MU":       "Foundation - HBM3E AI Memory Stack",
    "LSCC":     "Foundation - Edge AI FPGA (Low Power)",
    "ARM":      "Royalty - CPU IP Licensing (Every Device)",
    "ARQQ":     "Defense - Post-Quantum Encryption SaaS",
    "PLTR":     "Foundation - AI Defense & Enterprise Analytics",
    "AMBA":     "Moonshot - Edge AI Vision SoC (Automotive)",
    "SMCI":     "Infrastructure - AI Server & Liquid Cooling",
}


# Her hisse icin 'Odak' (haber tarayicinin tetiklemesi gereken yatay sektor).
# Investor Overview'da Stratejik Rol kolonu altinda gosterilir.
STRATEGIC_FOCUS = {
    "NVTS": "Veri merkezi guc verimi + EV sarj/inverter (Tier-1 OEM)",
    "INDI": "L3+ FSD design wins (Tesla/VW/Hyundai SoC)",
    "IONQ": "AQ 64+ kübit ve oda sicakligi operasyonu",
    "RGTI": "Superconducting kübit olcekleme + error correction",
    "QUBT": "Fotonik kuantum networking + savunma kontrati",
    "LAES": "NIST PQC standartlari + Secure Element / RISC-V",
    "ATOM": "MST katman lisanslama + Foundry JDA (Intel/TSM/Samsung)",
    "AXTI": "InP/GaAs alttas + 6G ve Silicon Photonics altyapi",
    "WOLF": "Mohawk Valley SiC fab + 200mm gecisi",
    "ASML": "High-NA EUV teslimati + 2nm mantik dugum",
    "QBTS": "Advantage2 annealing + enterprise cloud quantum contract",
    "CRDO": "800G/1.6T AEC hyperscaler design win (NVDA/META/MSFT)",
    "ALAB": "PCIe Gen6 / CXL 3.0 retimer Tier-1 cloud ramp",
    "POET": "800G optical engine JDA + foundry partner ramp",
    "AEHR": "SiC/GaN wafer-level burn-in capacity expansion + yield tool order",
    "AVGO": "Custom XPU ASIC (Google TPU / Meta MTIA) volume ramp",
    "MRVL": "Custom AI silicon (AWS Trainium / cloud) design win",
    "VRT": "Hyperscaler AI rack power + liquid cooling capex order",
    "MU": "HBM3E allocation (NVDA Blackwell stack) + supply contract",
    "LSCC": "Edge AI FPGA automotive/industrial design win",
    "ARM": "v9 AI CPU licensing + datacenter Neoverse ramp",
    "ARQQ": "NIST PQC enterprise contract + government mandate",
    "PLTR": "DoD AI contract + AIP enterprise deployment scale",
    "AMBA": "L3 vision SoC Tier-1 OEM design win + AEC-Q100",
    "SMCI": "NVDA GB200 rack-scale server volume shipment",
}


def get_investor_category(ticker: str) -> str:
    return INVESTOR_CATEGORY.get(ticker.upper(), "Technology")


# Mevcut Apple piyasa degeri (~$3.5T, 2026 Q2). Hicbir hissenin
# 10y projeksiyonu bu degeri gecemez varsayimi (kullanici talebi).
APPLE_MARKET_CAP_USD = 3.5e12   # $3.5 trilyon
APPLE_MARKET_CAP_BN = 3_500     # billion USD


def get_absolute_market_cap_ceiling_usd() -> float:
    """10y projeksiyon icin global ust limit (Apple piyasa degeri)."""
    return APPLE_MARKET_CAP_USD


# Sektor liderinin guncel piyasa degeri (USD). Reality Check (Dizginleme)
# icin kullanilir: bir hissenin 10y projeksiyonu kendi sektor liderinin
# guncel market cap'ini gecemez (kullanici talebi).
# Rakamlar 2026 Q2 yaklasik.
SECTOR_LEADER_MARKET_CAP_USD = {
    "QUANTUM_COMPUTING": 3.3e12,  # NVDA cogu kuantum karsisi - 3.3T tekel
    "SIC_POWER":         150e9,   # STM/Infineon karisik - 150B
    "GAN_POWER":         150e9,   # STM/Infineon
    "EUV_LITHO":         400e9,   # ASML kendisi lider ~$400B
    "INP_GAAS":          15e9,    # Coherent/II-VI - $15B
    "AUTO_SOC":          800e9,   # TSLA / Mobileye ekosistemi
    "DUV_FOUNDRY":       500e9,   # TSMC
    "MST_LICENSING":     1.0e12,  # ASML/ARM gibi lisans devleri
    "SECURE_MCU":        80e9,    # NXP/STM/Infineon ortalama
    "AI_ACCEL":          3.3e12,  # NVDA $3.3T sektor lideri
    "MEMORY":            500e9,   # Samsung memory + SK Hynix
    "FOUNDRY_LEADING":   900e9,   # TSMC $900B
    "AI_INTERCONNECT":   3.3e12,  # NVDA ecosystem ceiling
    "SEMI_TEST_EQUIP":   150e9,   # Teradyne/Advantest
    "AI_DC_INFRA":       200e9,   # Eaton/Schneider class
    "CUSTOM_ASIC":       1.2e12,  # AVGO itself large
    "EDGE_AI_FPGA":      80e9,
    "CPU_IP":            150e9,   # ARM
    "PQC_SOFTWARE":      80e9,    # CRWD/PANW proxy
    "AI_ENTERPRISE_SW":  400e9,   # MSFT/SNOW proxy
    "DEFAULT":           500e9,   # Tanimsiz
}


# 'Reality Check' icin global benchmark cap: hicbir tekno hisse NVDA'yi
# gecemez (kullanici talebi). $3.3 trilyon, 2026 Q2 NVDA piyasa degeri.
NVDA_MARKET_CAP_USD = 3.3e12


# v8 GLOBAL HARD CAP: hicbir hisse 10y horizon'da mevcut fiyatinin 20x'ini
# gecemez (kullanici talebi). Sektor TAM cap'i ve per-ticker cap'i 20x'in
# ustundeyse 20x'e clip edilir. Bu kural Prophet logistic growth saturation
# saglar ve $23k AXTI-tipi outlier'lari yapisal olarak engeller.
GLOBAL_PRICE_CAP_MULTIPLIER_10Y = 20.0

# Tum hisseler icin 10y CAGR bandi tabani (kullanici talebi):
#   Min %15  -  Max %25
# Sektor CAGR bu bandin ustundeyse cap'lenir.
GLOBAL_CAGR_BAND_MIN_PCT = 15.0
GLOBAL_CAGR_BAND_MAX_PCT = 25.0


def get_global_price_cap_multiplier() -> float:
    return GLOBAL_PRICE_CAP_MULTIPLIER_10Y


def get_global_cagr_band() -> tuple[float, float]:
    return (GLOBAL_CAGR_BAND_MIN_PCT, GLOBAL_CAGR_BAND_MAX_PCT)


def get_sector_leader_cap_usd(ticker: str) -> float:
    """Hissenin sektor liderinin piyasa degeri (Reality Check ust siniri)."""
    sec = get_sector(ticker)
    return float(SECTOR_LEADER_MARKET_CAP_USD.get(
        sec, SECTOR_LEADER_MARKET_CAP_USD["DEFAULT"]))


def get_nvda_ceiling_usd() -> float:
    """NVDA piyasa degeri - 'Sektor Lideri Degerlemesi' global tavan."""
    return NVDA_MARKET_CAP_USD


# Hisse-bazli MUTLAK fiyat tavanlari (10y projeksiyon icin).
# Kullanici talebi: NVTS icin $100 outlier esigi.
# Bu cap, sektor TAM ve global cap'lerin DA USTUNDE bir kural - hard outlier
# filtresi.
TICKER_PRICE_CAP_10Y = {
    "NVTS": 100.0,   # GaN power semi - sektor CAGR %15-20 -> $100 outlier
    # ileride digerleri eklenebilir
}


def get_ticker_price_cap_10y(ticker: str) -> float | None:
    """Hisseye-ozel 10y fiyat tavani (varsa). None ise sektor mantigi kullanilir."""
    return TICKER_PRICE_CAP_10Y.get(ticker.upper())


# Hisse-bazli MAX CAGR (Cap multiplier alternatifi). NVTS icin %18 CAGR
# = 10 yilda ~5.2x. Bu, Prophet'in agresif tahminlerini dizginler.
TICKER_MAX_CAGR_PCT_10Y = {
    "NVTS": 20.0,    # GaN power semi sektor CAGR bandi %15-20 ust ucu
}


def get_ticker_max_cagr_10y(ticker: str) -> float | None:
    return TICKER_MAX_CAGR_PCT_10Y.get(ticker.upper())


# Fisher 'Scuttlebutt' (kulis arastirmasi) sorgu setleri.
# Cok yuksek Ar-Ge yogunlugu olan sirketler icin (Common Stocks and Uncommon
# Profits, Philip Fisher) cevre haberleri taraman gerekir:
#   1. Musteri / partner roportajlari
#   2. Eski calisan yorumlari
#   3. Tedarikci/rakip iliskileri
#   4. Patent davalari ve teknoloji deneylerinde sonuclar
SCUTTLEBUTT_QUERIES = {
    "ATOM": [
        "Atomera MST customer testimonial",
        "Atomera engineer review Glassdoor",
        "Mears Silicon Technology benchmark independent",
        "Atomera competitor reaction",
        "Atomera supplier relationship",
        "Atomera production yield results",
    ],
    "LAES": [
        "SEALSQ customer testimonial PQC secure element",
        "SEALSQ engineer review WISeKey",
        "VaultiTrust deployment customer",
        "RISC-V security secure enclave SEALSQ",
        "Matter Protocol certification SEALSQ chip",
        "post-quantum cryptography hardware adoption",
        "NIST CRYSTALS Kyber Dilithium silicon integration",
    ],
    "IONQ": [
        "IONQ enterprise customer testimonial",
        "IONQ engineer review",
        "IONQ vs IBM quantum benchmark independent",
        "IONQ partner reaction roadmap",
    ],
    "RGTI": [
        "Rigetti customer pilot result",
        "Rigetti engineer review",
        "Rigetti vs Google quantum benchmark",
    ],
    "WOLF": [
        "Wolfspeed Mohawk Valley employee review",
        "Wolfspeed customer SiC adoption EV",
        "Wolfspeed yield independent report",
    ],
    "ASML": [
        "ASML High-NA customer delivery delay",
        "ASML Veldhoven supplier relationship",
        "ASML engineer review competing companies",
    ],
    "QBTS": [
        "D-Wave Advantage quantum annealing customer",
        "D-Wave enterprise cloud quantum contract",
        "quantum annealing vs gate model benchmark",
    ],
    "CRDO": [
        "Credo AEC 800G hyperscaler design win",
        "active electrical cable AI rack adoption",
        "Credo customer testimonial datacenter",
    ],
    "ALAB": [
        "Astera Labs PCIe Gen6 CXL retimer ramp",
        "Astera Labs hyperscaler design win",
        "CXL fabric AI server adoption",
    ],
    "AEHR": [
        "Aehr Test SiC burn-in capacity order",
        "wafer level burn-in yield improvement",
        "Aehr customer Wolfspeed Navitas ramp",
    ],
    "POET": [
        "POET Technologies optical engine JDA",
        "silicon photonics 800G transceiver ramp",
        "POET foundry partner light source",
    ],
    "AVGO": [
        "Broadcom custom AI ASIC Google TPU",
        "Broadcom hyperscaler XPU volume ramp",
        "VMware AI networking synergies",
    ],
    "MRVL": [
        "Marvell custom AI silicon AWS",
        "Marvell datacenter electro-optics",
        "Marvell automotive ethernet AI",
    ],
    "VRT": [
        "Vertiv AI datacenter cooling order backlog",
        "hyperscaler liquid cooling capex Vertiv",
        "rack power density 48V AI infrastructure",
    ],
    "MU": [
        "Micron HBM3E NVDA allocation",
        "HBM supply contract shortage",
        "Micron AI memory capex expansion",
    ],
    "ARM": [
        "Arm v9 AI CPU licensing datacenter",
        "Neoverse hyperscaler custom chip",
        "Arm royalty per wafer smartphone AI",
    ],
    "ARQQ": [
        "Arqit quantum encryption government contract",
        "NIST post-quantum software enterprise",
        "symmetric key quantum safe deployment",
    ],
    "PLTR": [
        "Palantir AIP enterprise deployment",
        "Palantir DoD AI contract award",
        "Palantir government analytics scale",
    ],
    "SMCI": [
        "Super Micro NVDA GB200 server shipment",
        "AI server backlog liquid cooling",
        "Super Micro hyperscaler rack order",
    ],
}


def get_scuttlebutt_queries(ticker: str) -> list[str]:
    return SCUTTLEBUTT_QUERIES.get(ticker.upper(), [])


def get_sector(ticker: str) -> str:
    return TICKER_TO_SECTOR.get(ticker, "DEFAULT")


def get_tam_today_bn(ticker: str) -> float:
    """Bugunku sektor TAM ($bn)."""
    return float(SECTOR_TAM_BN_USD.get(get_sector(ticker),
                                         SECTOR_TAM_BN_USD["DEFAULT"]))


def get_tam_projected_bn(ticker: str, years: int = 10) -> float:
    """N yil sonra sektor TAM ($bn) - bilesik buyume."""
    sec = get_sector(ticker)
    cagr = SECTOR_TAM_CAGR_PCT.get(sec, SECTOR_TAM_CAGR_PCT["DEFAULT"])
    today = get_tam_today_bn(ticker)
    return round(today * ((1 + cagr / 100) ** years), 2)


def get_realistic_share_pct(ticker: str) -> float:
    """
    Bir sirketin makul olarak ele gecirebilecegi TAM payi (max).
    Tekel pozisyonu (ASML) icin %80, niche oyuncular icin %20.
    """
    monopolies = {"ASML": 80, "TSM": 55, "NVDA": 70}
    if ticker in monopolies:
        return monopolies[ticker]
    sec = get_sector(ticker)
    # Quantum/MST gibi early-stage icin %30 makul, kalanlar icin %25
    if sec in ("QUANTUM_COMPUTING", "MST_LICENSING", "SECURE_MCU"):
        return 30.0
    return 25.0


# Sektor bazli ortalama Price/Sales (P/S) carpanlari.
# Market Cap = Revenue x P/S. TAM (yillik gelir) -> Market Cap donusumu icin
# kullanilir. Yuksek-buyume tek sektorler icin yuksek katsayi.
SECTOR_PS_MULTIPLIER = {
    "QUANTUM_COMPUTING": 30,   # cok yuksek-buyume bekentisi, NTM negatif
    "SIC_POWER":         8,    # WOLF tarihsel ortalama
    "GAN_POWER":         12,
    "EUV_LITHO":         30,   # ASML tekel - tarihsel P/S 25-35
    "INP_GAAS":          5,
    "AUTO_SOC":          6,
    "DUV_FOUNDRY":       5,
    "MST_LICENSING":     40,   # ATOM cok yuksek-bekenti, niche, lisanslama
    "SECURE_MCU":        12,
    "AI_ACCEL":          25,   # NVDA premium - tarihsel boom donemi 30+
    "MEMORY":            4,
    "FOUNDRY_LEADING":   10,
    "AI_INTERCONNECT":   22,
    "SEMI_TEST_EQUIP":   8,
    "AI_DC_INFRA":       6,
    "CUSTOM_ASIC":       18,
    "EDGE_AI_FPGA":      10,
    "CPU_IP":            20,
    "PQC_SOFTWARE":      15,
    "AI_ENTERPRISE_SW":  12,
    "DEFAULT":           8,
}


def get_ps_multiplier(ticker: str) -> float:
    """Sektor P/S carpani - TAM'i piyasa degerine cevirmek icin."""
    sec = get_sector(ticker)
    return float(SECTOR_PS_MULTIPLIER.get(sec, SECTOR_PS_MULTIPLIER["DEFAULT"]))


def get_cap_multiplier(ticker: str) -> float:
    """
    Prophet logistic 'cap' icin fiyat carpani. Default 10x.
    Tekel ve cok kuvvetli moat (ASML, NVDA) icin 15x.
    Riskli/spekulatif (QUBT, LAES) icin 8x (TAM cok kucuk).
    """
    monopolies = {"ASML": 15, "NVDA": 15, "TSM": 12}
    if ticker in monopolies:
        return float(monopolies[ticker])
    sec = get_sector(ticker)
    if sec in ("QUANTUM_COMPUTING", "SECURE_MCU"):
        # Sektor cok hizli buyuyor ama TAM kucuk, fiyat 8x ile kapali
        return 8.0
    return 10.0
