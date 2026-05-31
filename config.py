"""
config.py - Merkezi yapilandirma
"""
from pathlib import Path

# Proje kok dizini
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Cekirdek izlenen hisseler (ABD) - Investor Executive Summary'de gosterilir.
# NVTS, QBTS, POET, ARQQ, SMCI kullanici portfoyune dahil edildi.
TICKERS = [
    "WOLF", "IONQ", "RGTI", "ATOM", "LAES", "NVTS",
    # Kullanici portfoyune eklenenler (Investor Executive Summary'ye dahil)
    "QBTS", "POET", "ARQQ", "SMCI",
]

# Genisletilmis radar - watchlist defaults
# - ABD yari iletken / kuantum
# - Avrupa (ASML litografi)
# - Cin (Hong Kong listed: SMIC, Hua Hong)
# AI + Kuantum cagi genisletmesi (Tier 1-3 tam paket).
# NOT: QBTS/POET/ARQQ/SMCI cekirdege tasindi; burada sadece geriye kalanlar.
AI_QUANTUM_WATCHLIST = [
    # Tier 1 - Moonshot / Infra / Royalty
    "CRDO", "ALAB", "AEHR",
    # Tier 2 - Foundation / Infrastructure
    "AVGO", "MRVL", "VRT", "MU", "LSCC", "ARM",
    # Tier 3 - Spekulatif / Niş
    "PLTR", "AMBA",
]
EXTRA_WATCHLIST = ["AXTI", "INDI", "QUBT", "ASML"] + AI_QUANTUM_WATCHLIST
CHINA_TICKERS = ["0981.HK", "1347.HK"]
ALL_WATCHLIST_DEFAULTS = EXTRA_WATCHLIST + CHINA_TICKERS

# Sirket isimleri (haber aramasi icin)
COMPANY_NAMES = {
    # Core
    "WOLF": "Wolfspeed semiconductor",
    "IONQ": "IonQ quantum computing",
    "RGTI": "Rigetti Computing quantum",
    "ATOM": "Atomera semiconductor",
    "LAES": "SEALSQ Corp post-quantum cryptography secure element",
    # Watchlist extras
    "AXTI": "AXT Inc indium phosphide gallium arsenide",
    "NVTS": "Navitas Semiconductor gallium nitride GaN",
    "INDI": "indie Semiconductor automotive SoC",
    "QUBT": "Quantum Computing Inc photonic",
    "ASML": "ASML extreme ultraviolet lithography",
    # China
    "0981.HK": "SMIC Semiconductor Manufacturing International",
    "1347.HK": "Hua Hong Semiconductor",
    # AI + Kuantum cagi (2026 genisletme)
    "QBTS": "D-Wave Quantum annealing quantum computing",
    "CRDO": "Credo Technology active electrical cable AI interconnect",
    "ALAB": "Astera Labs PCIe CXL retimer AI datacenter",
    "AEHR": "Aehr Test Systems SiC GaN burn-in test equipment",
    "POET": "POET Technologies silicon photonics optical engine",
    "AVGO": "Broadcom custom AI ASIC networking",
    "MRVL": "Marvell Technology custom AI silicon datacenter",
    "VRT": "Vertiv data center power cooling infrastructure",
    "MU": "Micron Technology HBM DRAM AI memory",
    "LSCC": "Lattice Semiconductor low power FPGA edge AI",
    "ARM": "Arm Holdings CPU IP licensing edge AI",
    "ARQQ": "Arqit Quantum encryption post-quantum software",
    "PLTR": "Palantir AI defense enterprise analytics",
    "AMBA": "Ambarella edge AI vision SoC automotive",
    "SMCI": "Super Micro Computer AI server liquid cooling",
}

# Para birimi etiketi (yfinance otomatik dondurmezse fallback)
CURRENCY_HINTS = {
    "0981.HK": "HKD",
    "1347.HK": "HKD",
    "ASML":    "EUR",   # ASML.AS Avrupa tabanli, ASML US ADR USD
}

# USD/HKD/EUR/CNY -> USD karsilastirma icin (opsiyonel)
FX_TO_USD = {
    "USD": 1.0,
    "HKD": 0.128,    # ~7.8 HKD/USD
    "EUR": 1.08,
    "CNY": 0.138,
    "GBP": 1.27,
}

# Veri cekme
HISTORY_PERIOD = "5y"          # yillik grafik icin
HISTORY_INTERVAL = "1d"
REFRESH_MINUTES = 15

# Teknik indikatörler
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ML
ML_TRAIN_DAYS = 252 * 2        # ~2 yil egitim
ML_TEST_RATIO = 0.2
RANDOM_STATE = 42

# Sinyal esikleri
SENTIMENT_BULLISH = 0.15       # compound > bu -> pozitif haber
SENTIMENT_BEARISH = -0.15
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 70
BUY_PROB_THRESHOLD = 0.55      # ML olasilik esigi

# Uyari: cok guclu firsat
ALERT_SENTIMENT_MIN = 0.25
ALERT_RSI_MAX = 55             # asiri alimda alim onerme
