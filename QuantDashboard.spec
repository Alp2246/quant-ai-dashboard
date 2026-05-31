# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Quant AI Dashboard --onefile build.

Build:
    pyinstaller QuantDashboard.spec --noconfirm --clean
"""
from PyInstaller.utils.hooks import (collect_all, collect_data_files,
                                       collect_submodules)
import os

block_cipher = None

# ---------------------------------------------------------------------
# Project Python modules - bundle datas + hidden imports
# ---------------------------------------------------------------------
PROJECT_MODULES = [
    "alerts", "backtest", "black_litterman", "capex_watch",
    "cash_runway", "competitor_benchmark", "config", "correlation_matrix",
    "critical_news", "data_fetcher", "dca_calculator", "engineering_notes",
    "executive_brief", "feature_importance", "forecasting", "fundamentals",
    "geopolitics", "hardware_intel", "investor_summary", "master_score",
    "milestones", "ml_model", "moat_analysis", "monte_carlo",
    "moonshot_detector", "notifications", "paper_portfolio", "patent_watch",
    "purged_cv", "radar_watchlist", "reddit_sentiment", "research_agent",
    "risk_distribution", "sector_intelligence", "sector_tam", "semi_cycle",
    "sentiment_analysis", "strategic_overlays", "technical_indicators",
    "telegram_notifier", "visionary_goals", "volatility_smile",
    "phone_app_server",
]

# ---------------------------------------------------------------------
# Collect-all for problematic packages (streamlit/prophet/xgboost/plotly)
# ---------------------------------------------------------------------
def _safe_collect_all(name):
    try:
        return collect_all(name)
    except Exception:
        return [], [], []

streamlit_datas, streamlit_bins, streamlit_hidden = _safe_collect_all("streamlit")
plotly_datas, plotly_bins, plotly_hidden = _safe_collect_all("plotly")
prophet_datas, prophet_bins, prophet_hidden = _safe_collect_all("prophet")
cmdstan_datas, cmdstan_bins, cmdstan_hidden = _safe_collect_all("cmdstanpy")
xgboost_datas, xgboost_bins, xgboost_hidden = _safe_collect_all("xgboost")
yf_datas, yf_bins, yf_hidden = _safe_collect_all("yfinance")
sklearn_hidden = collect_submodules("sklearn")
altair_datas, altair_bins, altair_hidden = _safe_collect_all("altair")
pyarrow_datas, pyarrow_bins, pyarrow_hidden = _safe_collect_all("pyarrow")
holidays_datas, _, holidays_hidden = _safe_collect_all("holidays")
plyer_datas, plyer_bins, plyer_hidden = _safe_collect_all("plyer")

# ---------------------------------------------------------------------
# Datas (project files + JSON config)
# ---------------------------------------------------------------------
datas = [
    ("app.py", "."),
    ("milestones.json", "."),
]
for m in PROJECT_MODULES:
    fname = f"{m}.py"
    if os.path.exists(fname):
        datas.append((fname, "."))

# Markdown files (icin gerekirse - referans)
for md in ("Math_Specs.md", "README.md", "LIBRARIES.md", "OGRENME_KITAPLARI.md",
           "KURULUM_ARKADAS.md", "APK_OLUSTURMA.md"):
    if os.path.exists(md):
        datas.append((md, "."))

# PWA telefon uygulamasi (phone_app/ -> bundle icinde phone_app/)
if os.path.isdir("phone_app"):
    for root, _dirs, files in os.walk("phone_app"):
        for fn in files:
            if fn.endswith(".py") and fn == "generate_icons.py":
                continue
            src = os.path.join(root, fn)
            rel = os.path.relpath(root, "phone_app")
            dest = os.path.join("phone_app", rel) if rel != "." else "phone_app"
            datas.append((src, dest))

# Library data
datas += streamlit_datas + plotly_datas + prophet_datas + cmdstan_datas
datas += xgboost_datas + yf_datas + altair_datas + pyarrow_datas
datas += holidays_datas + plyer_datas

binaries = (streamlit_bins + plotly_bins + prophet_bins + cmdstan_bins +
             xgboost_bins + yf_bins + altair_bins + pyarrow_bins + plyer_bins)

# ---------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------
hiddenimports = list(set(
    streamlit_hidden + plotly_hidden + prophet_hidden + cmdstan_hidden +
    xgboost_hidden + yf_hidden + sklearn_hidden + altair_hidden +
    pyarrow_hidden + holidays_hidden + plyer_hidden +
    PROJECT_MODULES + [
        "yfinance", "yfinance.utils",
        "textblob", "textblob.tokenizers", "textblob.taggers",
        "nltk", "nltk.tokenize", "nltk.sentiment", "nltk.sentiment.vader",
        "feedparser", "joblib", "joblib.externals",
        "plyer", "plyer.platforms", "plyer.platforms.win",
        "plyer.platforms.win.notification",
        "PIL", "PIL.Image", "PIL._tkinter_finder",
        "bs4", "beautifulsoup4", "lxml",
        "scipy", "scipy.sparse.csgraph._validation",
        "scipy.spatial.transform._rotation_groups",
        "statsmodels", "statsmodels.tsa", "statsmodels.tsa.api",
        "dotenv", "python_dotenv",
        "streamlit.web.cli", "streamlit.runtime",
        "streamlit.runtime.scriptrunner",
        "streamlit.runtime.scriptrunner.magic_funcs",
        "streamlit.runtime.caching",
        "streamlit.elements",
        "click", "tornado", "watchdog", "validators",
        "pandas", "numpy", "pandas.io.formats.style",
    ]
))

# ---------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------
a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "PyQt5", "PyQt6", "PySide2", "PySide6",
        "IPython", "jupyter", "notebook", "ipykernel",
        "wx", "test", "tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="QuantDashboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,                 # Konsol gozuksun (Streamlit loglari)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
