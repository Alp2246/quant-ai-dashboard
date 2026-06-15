"""
alpha_engine.config
-------------------
Tum servis ayarlarinin tek noktasi. Ortam degiskenleri (.env) > defaults.

Kullanim:
    from config import settings
    settings.SEC_USER_AGENT
    settings.LOG_LEVEL

Tasarim notlari:
    * Hicbir secret koda gomulmez; sadece .env'den okunur.
    * Bos/eksik secret = ilgili kaynak otomatik DISABLED (servis cokmesin).
    * Dataclass + property kullanildi (3. parti bagimliligi olmasin).
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
#  .env yukleyici (python-dotenv bagimliligi olmadan minimal parser)
# ---------------------------------------------------------------------------
def _load_dotenv(path: Path) -> None:
    """Basit .env parser - python-dotenv yoksa da calisir."""
    if not path.is_file():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)
    except Exception as exc:
        sys.stderr.write(f"[config] .env okunamadi: {exc}\n")


BASE_DIR = Path(__file__).resolve().parent
_load_dotenv(BASE_DIR / ".env")


# ---------------------------------------------------------------------------
#  Yardimcilar
# ---------------------------------------------------------------------------
def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.environ.get(key, default)
    if val is None or val == "":
        return None
    return val


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    raw = _env(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = _env(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_list(key: str, default: list[str]) -> list[str]:
    raw = _env(key)
    if raw is None:
        return list(default)
    return [s.strip() for s in raw.split(",") if s.strip()]


# ---------------------------------------------------------------------------
#  Settings dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    # ---- Genel runtime ----
    APP_NAME: str = "quantai-alpha-engine"
    ENV: str = field(default_factory=lambda: _env("ENV", "dev"))
    TICK_SECONDS: int = field(default_factory=lambda: _env_int("TICK_SECONDS", 60))
    TASK_TIMEOUT: int = field(default_factory=lambda: _env_int("TASK_TIMEOUT", 50))
    SHUTDOWN_GRACE: int = field(default_factory=lambda: _env_int("SHUTDOWN_GRACE", 10))
    HEARTBEAT_FILE: Path = field(
        default_factory=lambda: BASE_DIR / "data" / "heartbeat.txt"
    )
    STATE_DIR: Path = field(default_factory=lambda: BASE_DIR / "data" / "state")
    LOG_DIR: Path = field(default_factory=lambda: BASE_DIR / "data" / "logs")

    # ---- Loglama ----
    LOG_LEVEL: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    LOG_JSON: bool = field(default_factory=lambda: _env_bool("LOG_JSON", False))
    LOG_ROTATE_MB: int = field(default_factory=lambda: _env_int("LOG_ROTATE_MB", 20))
    LOG_BACKUPS: int = field(default_factory=lambda: _env_int("LOG_BACKUPS", 5))

    # ---- Ticker evreni ----
    TICKERS: list[str] = field(default_factory=lambda: _env_list(
        "TICKERS",
        [
            # Core
            "WOLF", "IONQ", "RGTI", "ATOM", "LAES", "NVTS", "QBTS",
            "POET", "ARQQ", "SMCI",
            # Watchlist
            "AXTI", "INDI", "QUBT", "ASML",
            "CRDO", "ALAB", "AEHR",
            "AVGO", "MRVL", "VRT", "MU", "LSCC", "ARM",
            "PLTR", "AMBA",
        ],
    ))

    # ---- Anomali tetikleri ----
    Z_TRIGGER: float = field(default_factory=lambda: _env_float("Z_TRIGGER", 3.0))
    COMPOSITE_TRIGGER: float = field(default_factory=lambda: _env_float(
        "COMPOSITE_TRIGGER", 4.0
    ))
    MIN_SIGNALS_FOR_ALPHA: int = field(default_factory=lambda: _env_int(
        "MIN_SIGNALS_FOR_ALPHA", 3
    ))
    ALERT_COOLDOWN_MIN: int = field(default_factory=lambda: _env_int(
        "ALERT_COOLDOWN_MIN", 60
    ))
    # Cekirdek Master Score Telegram (score_job) — dakika
    MASTER_SCORE_INTERVAL_MIN: int = field(default_factory=lambda: _env_int(
        "MASTER_SCORE_INTERVAL_MIN", 240
    ))

    # ---- Kaynak: SEC EDGAR (zorunlu User-Agent) ----
    SEC_USER_AGENT: Optional[str] = field(default_factory=lambda: _env(
        "SEC_USER_AGENT"
    ))

    # ---- Kaynak: Reddit ----
    REDDIT_CLIENT_ID: Optional[str] = field(default_factory=lambda: _env(
        "REDDIT_CLIENT_ID"
    ))
    REDDIT_CLIENT_SECRET: Optional[str] = field(default_factory=lambda: _env(
        "REDDIT_CLIENT_SECRET"
    ))
    REDDIT_USER_AGENT: Optional[str] = field(default_factory=lambda: _env(
        "REDDIT_USER_AGENT", "quantai-alpha/0.1"
    ))

    # ---- Kaynak: Polygon (options unusual activity) ----
    POLYGON_API_KEY: Optional[str] = field(default_factory=lambda: _env(
        "POLYGON_API_KEY"
    ))

    # ---- Notifier: Telegram ----
    TELEGRAM_BOT_TOKEN: Optional[str] = field(default_factory=lambda: _env(
        "TELEGRAM_BOT_TOKEN"
    ))
    # Birden fazla kullanici icin virgulle ayir:
    #   TELEGRAM_CHAT_ID=5309279314,123456789
    TELEGRAM_CHAT_ID: Optional[str] = field(default_factory=lambda: _env(
        "TELEGRAM_CHAT_ID"
    ))

    # ---- HTTP defaults ----
    HTTP_TIMEOUT: int = field(default_factory=lambda: _env_int("HTTP_TIMEOUT", 20))
    HTTP_MAX_RETRIES: int = field(default_factory=lambda: _env_int(
        "HTTP_MAX_RETRIES", 3
    ))
    HTTP_CONCURRENCY: int = field(default_factory=lambda: _env_int(
        "HTTP_CONCURRENCY", 8
    ))

    # ----------------------------------------------------------------------
    #  Convenience flags - kaynak etkin mi?
    # ----------------------------------------------------------------------
    @property
    def sec_enabled(self) -> bool:
        return bool(self.SEC_USER_AGENT)

    @property
    def reddit_enabled(self) -> bool:
        return bool(self.REDDIT_CLIENT_ID and self.REDDIT_CLIENT_SECRET)

    @property
    def polygon_enabled(self) -> bool:
        return bool(self.POLYGON_API_KEY)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID)

    @property
    def telegram_chat_ids(self) -> list[str]:
        """Virgulle ayrilmis tum chat_id'lerin listesi."""
        if not self.TELEGRAM_CHAT_ID:
            return []
        return [s.strip() for s in self.TELEGRAM_CHAT_ID.split(",") if s.strip()]

    def health_summary(self) -> dict[str, object]:
        if self.reddit_enabled:
            social = "reddit_api"
        else:
            social = "reddit_rss+google_news"
        return {
            "app": self.APP_NAME,
            "env": self.ENV,
            "tick_seconds": self.TICK_SECONDS,
            "n_tickers": len(self.TICKERS),
            "sources": {
                "sec_edgar": self.sec_enabled,
                "social": social,
                "reddit_api": self.reddit_enabled,
                "reddit_rss": not self.reddit_enabled,
                "google_news": not self.reddit_enabled,
                "polygon": self.polygon_enabled,
            },
            "notifiers": {"telegram": self.telegram_enabled},
        }


settings = Settings()


# ---------------------------------------------------------------------------
#  Logging - tek noktada yapilandirma
# ---------------------------------------------------------------------------
def setup_logging() -> logging.Logger:
    """
    Stdout + dosya (rotating) loglama. Tum modullerden logger = logging.getLogger(__name__)
    ile alinabilir; bu fonksiyon root logger'i yapilandirir.
    """
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    settings.STATE_DIR.mkdir(parents=True, exist_ok=True)
    settings.HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    fmt_text = "%(asctime)s %(levelname)-7s %(name)s :: %(message)s"
    fmt_json = (
        '{"ts":"%(asctime)s","lvl":"%(levelname)s","logger":"%(name)s",'
        '"msg":%(message)r}'
    )
    fmt = logging.Formatter(fmt_json if settings.LOG_JSON else fmt_text,
                             datefmt="%Y-%m-%d %H:%M:%S")

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    fh = logging.handlers.RotatingFileHandler(
        settings.LOG_DIR / "alpha_engine.log",
        maxBytes=settings.LOG_ROTATE_MB * 1024 * 1024,
        backupCount=settings.LOG_BACKUPS,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # 3. parti kutuphane loglarini sessize alalim
    for noisy in ("urllib3", "asyncio", "aiohttp.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger(settings.APP_NAME)


__all__ = ["settings", "setup_logging", "Settings", "BASE_DIR"]
