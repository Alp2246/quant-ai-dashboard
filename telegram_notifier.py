"""
telegram_notifier.py - Telegram Bot push bildirimleri (telefon).

Kullanim:
  1. Telegram'da @BotFather ile yeni bot olustur, token al.
  2. Botunu ac, /start gonder.
  3. Bu modulun get_chat_id_from_updates() ile chat_id al.
  4. config'i ~/.quant_dashboard/telegram.json icine yaz:
     {
       "bot_token": "1234567890:AAE...",
       "chat_id": "123456789",
       "enabled": true,
       "min_severity": "KRITIK"
     }

Bildirim notifications.py'den otomatik tetiklenir.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Konfig dosyasi - kullanicinin home klasorunde (EXE bundle disinda)
CONFIG_DIR = Path(os.path.expanduser("~")) / ".quant_dashboard"
CONFIG_FILE = CONFIG_DIR / "telegram.json"

# Severity siralamasi (mesaj sentinel)
SEVERITY_ORDER = {"BILGI": 0, "GUCLU": 1, "UYARI": 2, "KRITIK": 3}
DEFAULT_MIN_SEVERITY = "KRITIK"


def format_backtest_metadata(metadata: dict | None) -> str:
    """Backtest varsayimlarini tek satirlik Telegram ozeti yap."""
    if not metadata:
        return ""
    try:
        return (
            f"\n<b>Backtest:</b> entry=<code>{metadata.get('entry_execution', '-')}</code>, "
            f"exit=<code>{metadata.get('signal_exit_execution', '-')}</code>, "
            f"hold=<code>{int(metadata.get('holding_days', 0))}d</code>, "
            f"rt_cost=<code>{float(metadata.get('roundtrip_cost_bps', 0)):.0f}bps</code>"
        )
    except Exception:
        return ""


# ---------------------------------------------------------------------
# Config yukleme / kaydetme
# ---------------------------------------------------------------------
def load_config() -> dict:
    """Telegram config'i diskten yukle. Yoksa default bos config."""
    if not CONFIG_FILE.exists():
        return {"bot_token": "", "chat_id": "", "enabled": False,
                "min_severity": DEFAULT_MIN_SEVERITY}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cfg.setdefault("enabled", False)
        cfg.setdefault("min_severity", DEFAULT_MIN_SEVERITY)
        cfg.setdefault("bot_token", "")
        cfg.setdefault("chat_id", "")
        return cfg
    except Exception as e:
        logger.warning("Telegram config okuma hata: %s", e)
        return {"bot_token": "", "chat_id": "", "enabled": False,
                "min_severity": DEFAULT_MIN_SEVERITY}


def save_config(cfg: dict) -> bool:
    """Telegram config'i diske kaydet."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error("Telegram config yazma hata: %s", e)
        return False


def is_configured() -> bool:
    cfg = load_config()
    return bool(cfg.get("enabled") and cfg.get("bot_token") and cfg.get("chat_id"))


# ---------------------------------------------------------------------
# Bot uzerinden chat_id'yi otomatik bul (kullanici /start gonderdikten sonra)
# ---------------------------------------------------------------------
def get_chat_id_from_updates(bot_token: str) -> tuple[str | None, str | None]:
    """
    Botun son guncellemelerinden chat_id'yi cek.
    Kullanici @YourBot'a /start gonderdikten sonra calistirilmali.

    Returns: (chat_id, username) veya (None, error_msg).
    """
    if not bot_token:
        return None, "Bot token bos"
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if not data.get("ok"):
            return None, f"Telegram API: {data.get('description', 'unknown')}"
        updates = data.get("result", [])
        if not updates:
            return None, ("Henuz mesaj yok. Once Telegram'da botuna "
                            "/start gonder, sonra tekrar dene.")
        # En son mesajdan chat al
        last = updates[-1]
        msg = last.get("message") or last.get("edited_message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        username = chat.get("username") or chat.get("first_name", "user")
        if chat_id:
            return str(chat_id), username
        return None, "Mesaj bulundu ama chat_id okunamadi"
    except requests.RequestException as e:
        return None, f"Aglerme hata: {e}"
    except Exception as e:
        return None, f"Beklenmedik hata: {e}"


# ---------------------------------------------------------------------
# Mesaj gonder
# ---------------------------------------------------------------------
def send_message(text: str, parse_mode: str = "HTML",
                  disable_notification: bool = False,
                  bot_token: str | None = None,
                  chat_id: str | None = None) -> bool:
    """
    Telegram'a mesaj gonder. Config'den otomatik token/chat_id okur,
    parametre verilirse onu kullanir.
    """
    cfg = load_config()
    bot_token = bot_token or cfg.get("bot_token", "")
    chat_id = chat_id or cfg.get("chat_id", "")
    if not bot_token or not chat_id:
        logger.debug("Telegram config eksik, mesaj atlandi")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:4096],  # Telegram limiti
        "parse_mode": parse_mode,
        "disable_notification": disable_notification,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return True
        logger.warning("Telegram %s: %s", r.status_code, r.text[:200])
        return False
    except requests.RequestException as e:
        logger.warning("Telegram gonderim hata: %s", e)
        return False


def test_connection(bot_token: str, chat_id: str) -> tuple[bool, str]:
    """Config kaydetmeden test mesaji gonder."""
    if not bot_token or not chat_id:
        return False, "Token veya chat_id bos"
    msg = (f"<b>🧪 Quant AI Dashboard - Test</b>\n\n"
            f"Telegram bildirimleri AKTIF.\n"
            f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n\n"
            f"✅ Artik kritik haberler telefonuna gelecek.")
    ok = send_message(msg, bot_token=bot_token, chat_id=chat_id)
    if ok:
        return True, "Test mesaji gonderildi - Telegram'a bak!"
    return False, "Mesaj gonderilemedi - token/chat_id yanlis olabilir"


# ---------------------------------------------------------------------
# Kritik tetikleyici icin HTML formatlama
# ---------------------------------------------------------------------
SEVERITY_EMOJI = {
    "KRITIK": "🚨",
    "UYARI":  "⚠️",
    "GUCLU":  "📈",
    "BILGI":  "ℹ️",
}

SEVERITY_BG = {  # Telegram'da bg yok ama sentinel olarak metinde
    "KRITIK": "🔴",
    "UYARI":  "🟠",
    "GUCLU":  "🟡",
    "BILGI":  "🔵",
}


def format_critical_event(ticker: str, event: dict) -> str:
    """Bir kritik tetikleyiciyi Telegram HTML formatina cevir."""
    severity = event.get("severity", "BILGI")
    emoji = SEVERITY_EMOJI.get(severity, "🔔")
    bg = SEVERITY_BG.get(severity, "⚪")
    title = event.get("title", "Kritik Olay")
    message = event.get("message", "")
    event_id = event.get("event_id", "")
    bt_meta = format_backtest_metadata(event.get("backtest_metadata"))

    ts = datetime.now().strftime("%H:%M")

    # HTML escaping minimal - title/message zaten cleansed icerikte
    body = (
        f"{bg} <b>{title}</b>\n\n"
        f"<b>Hisse:</b> {ticker}\n"
        f"<b>Seviye:</b> {emoji} <code>{severity}</code>\n"
        f"<b>Olay ID:</b> <code>{event_id}</code>\n"
        f"<b>Saat:</b> {ts}\n\n"
        f"{message}\n\n"
        f"{bt_meta}\n"
        f"<i>Quant AI Dashboard - Master Score v9</i>"
    )
    return body


def push_critical_event(ticker: str, event: dict) -> bool:
    """
    Notifications.py'den cagrilir. Severity filtresi uygular ve gonderir.
    """
    cfg = load_config()
    if not cfg.get("enabled"):
        return False
    min_sev = cfg.get("min_severity", DEFAULT_MIN_SEVERITY)
    ev_sev = event.get("severity", "BILGI")
    if SEVERITY_ORDER.get(ev_sev, 0) < SEVERITY_ORDER.get(min_sev, 3):
        return False
    text = format_critical_event(ticker, event)
    return send_message(text, parse_mode="HTML")


def push_master_score_alert(ticker: str, score: float, rating: str,
                            metadata: dict | None = None) -> bool:
    """Master Score >= 85 olunca ozel kritik mesaj."""
    if not load_config().get("enabled"):
        return False
    if score < 85:
        return False
    ts = datetime.now().strftime("%H:%M")
    bt_meta = format_backtest_metadata(metadata)
    text = (
        f"🔴 <b>KRITIK ALIM SINYALI</b>\n\n"
        f"<b>Hisse:</b> {ticker}\n"
        f"<b>Master Score:</b> <code>{score:.1f}/100</code>\n"
        f"<b>Rating:</b> {rating}\n"
        f"<b>Saat:</b> {ts}\n\n"
        f"{bt_meta}\n"
        f"<i>Dashboard'a bak: 🎯 Detail sekmesi -> {ticker}</i>"
    )
    return send_message(text, parse_mode="HTML")
