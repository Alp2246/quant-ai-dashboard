"""
notifications.py - Masaustu bildirim + log dosyasi
Master Score >= 85 ise KRITIK ALIM tetigi
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from config import BASE_DIR

logger = logging.getLogger(__name__)

LOG_FILE = BASE_DIR / "alerts.log"
CRITICAL_THRESHOLD = 85


def write_log(message: str, level: str = "INFO"):
    """alerts.log dosyasina yaz."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.warning("Log yazma hatasi: %s", e)


def desktop_notify(title: str, message: str, app_name: str = "Quant AI"):
    """Windows toast bildirimi (plyer)."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name=app_name,
            timeout=10,
        )
        return True
    except Exception as e:
        logger.warning("Bildirim hatasi: %s", e)
        return False


def handle_master_score(ticker: str, score: float, rating: str,
                        details: dict | None = None) -> dict:
    """
    Master Score'a gore karar al (verdict_rules ile uyumlu):
      KRITIK ALIM / GUCLU AL -> toast + log + Telegram
    """
    from verdict_rules import is_push_worthy, verdict_for
    rating = rating or verdict_for(score)
    result = {"notified": False, "logged": False, "rating": rating}

    if is_push_worthy(rating) or score >= CRITICAL_THRESHOLD:
        msg = (f"{ticker}: Master Score {score}/100 - {rating}"
               + (f"  (tech={details.get('technical')} sent={details.get('sentiment')} "
                  f"fund={details.get('fundamental')})" if details else ""))
        write_log(msg, level="KRITIK")
        ok = desktop_notify(
            title=f"KRITIK ALIM: {ticker}",
            message=f"Master Score: {score}/100\n{rating}",
        )
        # Telegram push (telefona)
        try:
            from telegram_notifier import push_master_score_alert
            tg_ok = push_master_score_alert(ticker, score, rating)
            result["telegram"] = tg_ok
        except Exception as e:
            logger.debug("telegram push atlandi: %s", e)
        result["notified"] = ok
        result["logged"] = True

    elif score >= 70:
        msg = f"{ticker}: Master Score {score}/100 - {rating}"
        write_log(msg, level="GUCLU")
        result["logged"] = True

    return result


# ---------------------------------------------------------------------------
# Kritik esik tetik bildirimi (v8 eksiklik #3)
# NVTS Tier-1 OEM, LAES NIST integration, ATOM JDA gibi 'haberden cikan'
# tetikleyici olaylarda popup ver. Session bazli idempotency (ayni event
# tekrar gosterilmez) state_file ile saglanir.
# ---------------------------------------------------------------------------
import json
TRIGGER_STATE_FILE = BASE_DIR / "data" / "trigger_state.json"


def _load_trigger_state() -> dict:
    if not TRIGGER_STATE_FILE.exists():
        return {}
    try:
        with open(TRIGGER_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_trigger_state(state: dict):
    try:
        TRIGGER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TRIGGER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("trigger state yazma: %s", e)


# Hisse -> kritik tetikleyici aktivasyon kontrolu
# (sonuc dict path'lerinden boolean cikar)
def _detect_triggers(ticker: str, result: dict) -> list[dict]:
    """
    Sonuc dict'inden 'haberden cekilebilecek kritik tetikleyici' olaylari
    cikar. Her tetikleyici:
      { event_id, title, message, severity }
    """
    triggers = []
    so = (result.get("strategic_overlay") or {})
    details = so.get("details", {}) or {}
    tk = ticker.upper()

    # NVTS - Tier-1 OEM esigi
    if tk == "NVTS" and details.get("tier1_threshold_crossed"):
        oems = details.get("tier1_oems") or []
        triggers.append({
            "event_id": f"{tk}_TIER1_OEM",
            "title": "🚀 NVTS Tier-1 OEM ESIGI GECILDI",
            "message": ("Tier-1 OEM ana tedarik anlasmasi tetiklendi"
                          + (f" ({', '.join(oems)})" if oems else "")
                          + ". J-Curve agresif EKLE sinyali."),
            "severity": "KRITIK",
        })
    if tk == "NVTS" and details.get("dc_power_active"):
        triggers.append({
            "event_id": f"{tk}_NVDA_DC_POWER",
            "title": "🖥️ NVTS DC Power Tailwind",
            "message": ("NVIDIA Blackwell/rack-scale 48V power haberi aktif - "
                          "NVTS AI DC ruzgari proxy katalisti tetiklendi."),
            "severity": "GUCLU",
        })

    # LAES - NIST PQC HW silicon entegrasyonu
    if tk == "LAES" and details.get("nist_integration"):
        triggers.append({
            "event_id": f"{tk}_NIST_PQC_INTEGRATION",
            "title": "🔐 LAES NIST PQC HW Onayi",
            "message": ("CRYSTALS-Kyber/Dilithium QS7001'e donanim "
                          "entegrasyon haberi DOĞRULANDI - Q-Day katalisti."),
            "severity": "KRITIK",
        })
    if tk == "LAES" and details.get("demand_spike_active"):
        triggers.append({
            "event_id": f"{tk}_PQC_DEMAND_SPIKE",
            "title": "⚡ LAES PQC Demand Spike",
            "message": ("Q-Day demand spike haberi aktif - cybersec CAPEX "
                          "rüzgarı."),
            "severity": "GUCLU",
        })

    # ATOM - Foundry JDA (Joint Development Agreement)
    if tk == "ATOM" and (result.get("atom_exponential_mode")
                            or details.get("exponential_mode")):
        triggers.append({
            "event_id": f"{tk}_FOUNDRY_JDA",
            "title": "📜 ATOM Foundry JDA Imzasi",
            "message": ("Tier-1 Foundry JDA tetiklendi - 'Royalty per Wafer' "
                          "EXPONENTIAL CAGR moduna gecildi."),
            "severity": "KRITIK",
        })

    # AXTI - Cin Galyum/Germanyum ihracat lisansi degisikligi
    if tk == "AXTI":
        geo = (result.get("geo_risk") or {})
        if geo.get("critical_alert"):
            triggers.append({
                "event_id": f"{tk}_GA_GE_EXPORT_CONTROL",
                "title": "🚨 AXTI Cin Ihracat Kontrolu",
                "message": ("Cin Galyum/Germanyum ihracat lisansi degisikligi "
                              "tetiklendi - kritik risk."),
                "severity": "KRITIK",
            })

    # ML overfit teshisi (siddetli)
    ml = result.get("ml") or {}
    if ml.get("overfit_verdict") and "SIDDETLI" in ml["overfit_verdict"]:
        triggers.append({
            "event_id": f"{tk}_ML_OVERFIT",
            "title": f"⚠️ {tk} ML Modeli Overfit",
            "message": (f"Lopez de Prado Purged CV: overfit gap "
                          f"{ml.get('overfitting_gap', 0):+.2f} - ML "
                          f"olasiligina guvenme."),
            "severity": "UYARI",
        })

    return triggers


def handle_critical_triggers(ticker: str, result: dict) -> list[dict]:
    """
    Tum kritik tetikleyicileri tespit et, idempotent sekilde bildirim ver.
    Ayni event_id zaten gosterilmisse tekrar gosterilmez (state file'da
    tutulur, 7 gun sonra resetlenir).

    Returns: bu cagrida tetiklenmis (yeni) events listesi
    """
    triggers = _detect_triggers(ticker, result)
    if not triggers:
        return []

    state = _load_trigger_state()
    now_ts = datetime.now().isoformat()
    new_events = []
    seven_days = 7 * 24 * 3600

    for trg in triggers:
        eid = trg["event_id"]
        last = state.get(eid, {}).get("last_fired")
        if last:
            try:
                age = (datetime.now()
                          - datetime.fromisoformat(last)).total_seconds()
                if age < seven_days:
                    continue
            except Exception:
                pass
        ok = desktop_notify(title=trg["title"], message=trg["message"])
        write_log(f"TRIGGER {eid} - {trg['message']}", level=trg["severity"])
        # Telegram push (telefona)
        tg_ok = False
        try:
            from telegram_notifier import push_critical_event
            tg_ok = push_critical_event(ticker, trg)
        except Exception as e:
            logger.debug("telegram trigger push atlandi: %s", e)
        state[eid] = {"last_fired": now_ts, "severity": trg["severity"],
                       "ticker": ticker, "title": trg["title"],
                       "message": trg["message"],
                       "telegram_sent": tg_ok}
        trg["notified"] = ok
        trg["telegram"] = tg_ok
        trg["ticker"] = ticker
        new_events.append(trg)

    if new_events:
        _save_trigger_state(state)
    return new_events


def get_log_tail(n: int = 30) -> list[str]:
    """Son N satir log."""
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return lines[-n:]
    except Exception:
        return []


def get_recent_critical_events(hours: int = 24) -> list[dict]:
    """
    Son <hours> saatte tetiklenmis KRITIK + UYARI olaylari dondur.
    Banner'da gosterilmek uzere.

    Returns: [{event_id, ticker, title, message, severity, last_fired,
                hours_ago}, ...]
    """
    state = _load_trigger_state()
    if not state:
        return []
    now = datetime.now()
    events = []
    for eid, data in state.items():
        last = data.get("last_fired")
        if not last:
            continue
        try:
            ts = datetime.fromisoformat(last)
            age_sec = (now - ts).total_seconds()
            if age_sec > hours * 3600:
                continue
            sev = data.get("severity", "BILGI")
            # Yalnizca KRITIK ve UYARI'lari goster
            if sev not in ("KRITIK", "UYARI"):
                continue
            events.append({
                "event_id": eid,
                "ticker": data.get("ticker", eid.split("_")[0]),
                "title": data.get("title", eid),
                "message": data.get("message", ""),
                "severity": sev,
                "last_fired": last,
                "hours_ago": round(age_sec / 3600, 1),
                "telegram_sent": data.get("telegram_sent", False),
            })
        except Exception:
            continue
    # En yeni en uste
    events.sort(key=lambda x: x["last_fired"], reverse=True)
    return events
