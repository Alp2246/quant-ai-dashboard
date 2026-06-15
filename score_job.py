"""
score_job.py - Streamlit OLMADAN cekirdek hisseler icin Master Score + Telegram.

Oracle / arka plan icin: agir ML, research agent, capex taramasi YOK.
Ayni verdict_rules kullanilir -> tablo ile Telegram ayni dili konusur.

Calistirma:
    python score_job.py
    python score_job.py --no-telegram
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# alpha_engine ile config cakismasini onle (ayri process olarak da calistirilir)
BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))
_ae = str(BASE_DIR / "alpha_engine")
sys.path[:] = [p for p in sys.path if p != _ae and not p.replace("\\", "/").endswith("/alpha_engine")]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
LOG = logging.getLogger(__name__)
STATE_DIR = BASE_DIR / "alpha_engine" / "data" / "state"
STATE_FILE = STATE_DIR / "master_scores.json"
COOLDOWN_FILE = STATE_DIR / "master_alert_cooldown.json"
COOLDOWN_HOURS = 6


def _analyze_lite(ticker: str) -> dict:
    """PC ile ayni pipeline (ticker_analyze_core) — tutarli skor."""
    from ticker_analyze_core import score_summary

    try:
        r = score_summary(ticker)
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}
    if r.get("error"):
        return r
    return {
        "ticker": ticker,
        "master_score": r["master_score"],
        "rating": r.get("rating"),
        "verdict": r.get("verdict"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_cooldown() -> dict:
    if not COOLDOWN_FILE.exists():
        return {}
    try:
        return json.loads(COOLDOWN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cooldown(data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    COOLDOWN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _cooldown_ok(ticker: str, verdict: str) -> bool:
    from verdict_rules import is_push_worthy
    if not is_push_worthy(verdict):
        return False
    data = _load_cooldown()
    key = f"{ticker}:{verdict}"
    last = data.get(key)
    if not last:
        return True
    try:
        t0 = datetime.fromisoformat(last.replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - t0).total_seconds() / 3600
        return age_h >= COOLDOWN_HOURS
    except Exception:
        return True


def _mark_cooldown(ticker: str, verdict: str) -> None:
    data = _load_cooldown()
    data[f"{ticker}:{verdict}"] = datetime.now(timezone.utc).isoformat()
    _save_cooldown(data)


def _send_telegram(ticker: str, score: float, verdict: str) -> bool:
    """Alpha Engine telegram kanalini kullan."""
    ae_dir = BASE_DIR / "alpha_engine"
    if str(ae_dir) not in sys.path:
        sys.path.insert(0, str(ae_dir))
    from verdict_rules import emoji_for
    from src.notifiers.telegram_push import send_message

    icon = emoji_for(verdict)
    text = (
        f"{icon} <b>{verdict} — {ticker}</b>\n"
        f"Master Score: <b>{score:.1f}/100</b>\n"
        f"<i>Cekirdek izleme listesi (4 saatte bir guncellenir). "
        f"Ayni etiket {COOLDOWN_HOURS} saat icinde tekrar gonderilmez.</i>\n\n"
        f"📊 <a href=\"http://abozer-1:8080\">Dashboard</a>"
    )
    return send_message(text)


# Cekirdek liste (quant-dashboard/config.py ile ayni — alpha_engine config karisikligini onler)
CORE_TICKERS = [
    "WOLF", "IONQ", "RGTI", "ATOM", "LAES", "NVTS",
    "QBTS", "POET", "ARQQ", "SMCI",
]


def run(*, push_telegram: bool = True) -> dict:
    from verdict_rules import is_push_worthy

    results = {}
    alerts_sent = 0
    for t in CORE_TICKERS:
        try:
            r = _analyze_lite(t)
            results[t] = r
            if r.get("error"):
                continue
            v = r["verdict"]
            ms = r["master_score"]
            LOG.info("%s score=%.1f verdict=%s", t, ms, v)
            if push_telegram and is_push_worthy(v) and _cooldown_ok(t, v):
                if _send_telegram(t, ms, v):
                    _mark_cooldown(t, v)
                    alerts_sent += 1
        except Exception as exc:
            LOG.error("%s hata: %s", t, exc)
            results[t] = {"ticker": t, "error": str(exc)}

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "tickers": results,
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    LOG.info("Kaydedildi: %s | telegram=%d", STATE_FILE, alerts_sent)
    return payload


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--no-telegram", action="store_true")
    args = p.parse_args()
    run(push_telegram=not args.no_telegram)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
