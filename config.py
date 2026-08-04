"""
config.py - Merkezi yapilandirma
"""
import os as _os
from pathlib import Path

# Proje kok dizini
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Cekirdek izlenen hisseler (ABD) - Investor Executive Summary'de gosterilir.
# NVTS, QBTS, POET, ARQQ, SMCI kullanici portfoyune dahil edildi.
CORE_TICKERS = [
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

# --- Darbogaz tezi: kardes proje (aleabito_monitor) haritasindan gelen,
# ABD/Avrupa'da GERCEKTEN alinabilir isimler. Gerceklik Kontrolu bunlari da
# degerlendirir; boylece "darbogazi tutan sirket al-tut'u yendi mi?" sorusu
# tek bir hisseyle degil, sepetle test edilir.
# NOT: NBIS/CBRS/SNDK yakin tarihli listeleme — kisa gecmis, az islem cikar.
BOTTLENECK_WATCHLIST = [
    "LITE", "AAOI", "COHR", "POET",      # lazer / optik
    "AXTI",                                # InP alttas
    "SNDK", "MU",                          # bellek
    "NBIS", "CBRS",                        # hesaplama kapasitesi
    "AOSL", "POWI",                        # guc yari iletken
    "IBIDY",                               # ABF altlik (OTC ADR)
]

# Darbogaz isimleri cekirdek analize dahil edilsin mi?
# true  : her sekme (Ozet, Detay, Research Agent, Backtest, Radar...) kapsar.
#         Yukleme suresi artar (10 -> 21 hisse).
# false : yalnizca Gerceklik Kontrolu sekmesi degerlendirir.
# .env veya ortam degiskeni ile kapatilabilir: INCLUDE_BOTTLENECK_IN_CORE=false
INCLUDE_BOTTLENECK_IN_CORE = (
    _os.getenv("INCLUDE_BOTTLENECK_IN_CORE", "true").lower() == "true"
)

# Uygulamanin her yerinde kullanilan cekirdek liste
TICKERS = list(CORE_TICKERS)
if INCLUDE_BOTTLENECK_IN_CORE:
    for _t in BOTTLENECK_WATCHLIST:
        if _t not in TICKERS:
            TICKERS.append(_t)
CHINA_TICKERS = ["0981.HK", "1347.HK"]
ALL_WATCHLIST_DEFAULTS = EXTRA_WATCHLIST + CHINA_TICKERS

# Sirket isimleri (haber aramasi icin)
COMPANY_NAMES = {
    # --- Darbogaz tezi (aleabito_monitor haritasindan) ---
    "LITE": "Lumentum optical laser",
    "AAOI": "Applied Optoelectronics transceiver",
    "COHR": "Coherent photonics laser",
    "AXTI": "AXT indium phosphide substrate",
    "SNDK": "SanDisk NAND flash memory",
    "NBIS": "Nebius AI cloud GPU",
    "CBRS": "Cerebras AI inference chip",
    "AOSL": "Alpha Omega power semiconductor",
    "POWI": "Power Integrations power semiconductor",
    "IBIDY": "Ibiden ABF substrate packaging",
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

# Backtest / label horizon ortak varsayimlari
BACKTEST_LOOKBACK_YEARS = 2.0
# Gerceklik Kontrolu daha UZUN pencere kullanir: 2 yilda hisse basina ~10-15
# islem cikiyor ve n<30 oldugu icin hicbir hukum verilemiyordu. HISTORY_PERIOD
# zaten 5y cektiginden bu ek maliyet getirmez. Backtest sekmesi degismez.
REALITY_LOOKBACK_YEARS = 5.0
BACKTEST_HOLDING_DAYS = 20
BACKTEST_COMMISSION_BPS = 10.0
BACKTEST_SLIPPAGE_BPS = 5.0
PURGED_CV_HORIZON_DAYS = BACKTEST_HOLDING_DAYS
PURGED_CV_EMBARGO_DAYS = 5

# Sinyal esikleri
SENTIMENT_BULLISH = 0.15       # compound > bu -> pozitif haber
SENTIMENT_BEARISH = -0.15
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 70
BUY_PROB_THRESHOLD = 0.55      # ML olasilik esigi

# Uyari: cok guclu firsat
ALERT_SENTIMENT_MIN = 0.25
ALERT_RSI_MAX = 55             # asiri alimda alim onerme
