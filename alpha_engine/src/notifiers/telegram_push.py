"""
telegram_push - Onemli olay mesajlari Telegram'a (Turkce).
"""
from __future__ import annotations

import html
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import settings
from src.analytics.engine import AlphaEvent

LOG = logging.getLogger(__name__)
DASHBOARD_URL = "http://abozer-1:8080"
TR_TZ = timezone(timedelta(hours=3))  # Turkiye saati (UTC+3)


# Kaynak agirligi (en onemli haber secimi icin)
SOURCE_IMPORTANCE = {
    "sec_form4": 6.0,       # CEO/CFO PURCHASE - en guclu (kendi paralariyla)
    "sec_edgar": 5.0,       # SEC resmi - kanonik
    "polygon_options": 2.5,
    "google_news": 1.5,
    "reddit_rss": 1.0,
    "reddit": 1.0,
}


# Kaynak isimleri (Turkce + aciklama)
SOURCE_TR = {
    "sec_edgar": "SEC Resmi Bildirim (8-K)",
    "sec_form4": "Insider (CEO/CFO) Hisse Alimi",
    "google_news": "Haber",
    "reddit_rss": "Reddit Forumu",
    "reddit": "Reddit Forumu",
    "polygon_options": "Opsiyon Hareketi",
    "stocktwits": "StockTwits Sosyal",
}

# Kohort = sirket buyuklugu (Turkce)
COHORT_TR = {
    "MEGA":  "BUYUK ($200B+)",
    "MID":   "ORTA ($10B-$200B)",
    "SMALL": "KUCUK (<$10B)",
}

# Severity Turkce
SEVERITY_TR = {
    "KRITIK": "KRITIK ONEMDE",
    "YUKSEK": "YUKSEK ONEMDE",
}


def _esc(text: str) -> str:
    return html.escape(str(text or ""), quote=False)


def _ratio_label(current: float, mean: float) -> str:
    """'7.5 kat yukarida' gibi insan-okunabilir orani uretir."""
    if mean <= 0.01:
        return "normalde hic yok, simdi spike"
    ratio = current / mean
    if ratio >= 10:
        return f"normalin <b>{ratio:.0f} KATI</b> ustunde (olaganustu)"
    if ratio >= 5:
        return f"normalin <b>{ratio:.1f} kati</b> ustunde (cok yuksek)"
    if ratio >= 3:
        return f"normalin <b>{ratio:.1f} kati</b> ustunde (belirgin)"
    if ratio >= 2:
        return f"normalin <b>{ratio:.1f} kati</b> ustunde"
    return f"normalin biraz uzerinde (x{ratio:.1f})"


def _z_label(z: float) -> str:
    """Z-score'u kelimeyle aciklar."""
    if z >= 7:
        return "OLAGANUSTU SAPMA"
    if z >= 5:
        return "cok yuksek sapma"
    if z >= 4:
        return "yuksek sapma"
    if z >= 3:
        return "belirgin sapma"
    return "hafif sapma"


def _source_explanation(source: str, value: float, meta: dict) -> str:
    """Kaynaga ozel insan-dilinde aciklama."""
    if source == "sec_edgar":
        title = meta.get("title", "Resmi bildirim")
        return (
            f"Sirket SEC'e yeni bir <b>8-K</b> dosyaladi.\n"
            f"   <b>Konu:</b> {_esc(title[:140])}\n"
            f"   <i>8-K = sirketin yatirimcilara aciklamak ZORUNDA oldugu material olay "
            f"(satin alma, anlasma, CEO degisikligi, dava vs.).</i>"
        )
    if source == "sec_form4":
        usd = meta.get("purchase_usd", 0)
        insider = meta.get("insider_name", "")
        titles = meta.get("insider_titles") or []
        title_str = ", ".join(titles[:2]) if titles else "Insider"
        return (
            f"<b>INSIDER PURCHASE:</b> {_esc(title_str)} {_esc(insider[:80])}\n"
            f"   Aldigi tutar: <b>${usd:,.0f}</b>\n"
            f"   <i>Form 4 = yoneticinin kendi parasiyla hisse alimi. SEC'e 2 is gunu "
            f"icinde dosyalanir. Yonetici sirketin gelecegine inaniyor demektir; "
            f"haberden ONCE oluyor genelde.</i>"
        )
    if source == "google_news":
        title = meta.get("latest_title", "")
        articles = int(value)
        return (
            f"Son 6 saatte <b>{articles} haber</b> cikti.\n"
            f"   <b>Ornek:</b> {_esc(title[:140])}"
        )
    if source in ("reddit_rss", "reddit"):
        n = int(value)
        return (
            f"Son 1 saatte <b>{n} paylasim</b> Reddit yatirim forumlarinda hisseden bahsetti.\n"
            f"   <i>Genelde retail dalganin habercisi.</i>"
        )
    if source == "polygon_options":
        return (
            f"<b>Call/Put orani {value:.1f}x</b>. Yatirimcilar opsiyonda saldirgan "
            f"yukseliş bahsi yapıyor.\n   <i>Genelde haberden once gorulur.</i>"
        )
    return f"deger: {value:.1f}"


def _pick_headline_trigger(triggers: list) -> Optional[dict]:
    """En onemli kaynagi sec: source_importance * z. Insider buy > SEC > digerleri."""
    if not triggers:
        return None
    # 1. oncelik: Insider buying (CEO/CFO PURCHASE)
    insider = [
        t for t in triggers
        if t.get("source") == "sec_form4" and (t.get("raw_peak", 0) or 0) >= 2.0
    ]
    if insider:
        return max(insider, key=lambda t: t.get("raw_peak", 0) or 0)
    # 2. oncelik: SEC 8-K
    sec = [t for t in triggers if t.get("source") == "sec_edgar"]
    if sec:
        return max(sec, key=lambda t: t.get("z", 0) or 0)
    return max(
        triggers,
        key=lambda t: SOURCE_IMPORTANCE.get(t.get("source"), 0.5) * (t.get("z", 0) or 0),
    )


def _format_event_time(peak_age_h: float) -> tuple[str, str]:
    """
    (mutlak_saat, gore_olarak_kac_once) tuple uretir.
    Ornek: ("15:42", "23 dakika once")
    """
    now = datetime.now(TR_TZ)
    event_dt = now - timedelta(hours=peak_age_h)
    absolute = event_dt.strftime("%H:%M")

    minutes = int(peak_age_h * 60)
    if minutes < 1:
        relative = "AZ ONCE"
    elif minutes < 60:
        relative = f"{minutes} dakika once"
    elif minutes < 60 * 24:
        hours = minutes // 60
        mins = minutes % 60
        if mins == 0:
            relative = f"{hours} saat once"
        else:
            relative = f"{hours} saat {mins} dk once"
    else:
        days = minutes // (60 * 24)
        relative = f"{days} gun once"

    # Bugun degilse tarih de ekle
    if event_dt.date() != now.date():
        absolute = event_dt.strftime("%d %b %H:%M")

    return absolute, relative


def _headline_summary(t: dict) -> str:
    """En onemli haberin tek-cumlelik basligi."""
    source = t.get("source", "")
    meta = t.get("metadata") or {}
    if source == "sec_form4":
        usd = meta.get("purchase_usd", 0)
        insider = meta.get("insider_name", "")
        titles = meta.get("insider_titles") or []
        title_str = ", ".join(titles[:2]) if titles else "Insider"
        return (
            f"💰 <b>INSIDER BUY:</b> {_esc(title_str)} "
            f"<b>{_esc(insider[:60])}</b> ${usd:,.0f} aldi (kendi parasiyla)"
        )
    if source == "sec_edgar":
        title = meta.get("title", "Resmi SEC bildirimi")
        return f"📄 <b>SEC 8-K Resmi Bildirim:</b> {_esc(str(title)[:160])}"
    if source == "google_news":
        title = meta.get("latest_title", "")
        n = int(t.get("raw_peak", 0))
        if title:
            return f"📰 <b>Haber Patlamasi ({n} haber):</b> {_esc(str(title)[:160])}"
        return f"📰 <b>Haber Patlamasi:</b> son saatte {n} haber cikti"
    if source in ("reddit_rss", "reddit"):
        n = int(t.get("raw_peak", 0))
        return f"💬 <b>Reddit Spike:</b> {n} kez konusuldu (1 saat icinde)"
    if source == "polygon_options":
        ratio = t.get("raw_peak", 0)
        return f"📈 <b>Opsiyon Saldirisi:</b> Call/Put orani {ratio:.1f}x"
    return f"<b>{_esc(t.get('label', source))}</b>"


def format_message(ev: AlphaEvent) -> str:
    icon = "🚨" if ev.severity == "KRITIK" else "⚡"
    cohort_tr = COHORT_TR.get(getattr(ev, "cohort", "") or "", "—")
    severity_tr = SEVERITY_TR.get(ev.severity, ev.severity)
    n_sources = len(ev.triggers)

    # ============ EN ONEMLI HABER bolumu (en uste) ============
    head = _pick_headline_trigger(ev.triggers)
    headline_block = []
    if head is not None:
        absolute, relative = _format_event_time(head.get("peak_age_h", 0) or 0)
        headline_block = [
            "",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"⏰ <b>EN ONEMLI HABER — {absolute}</b>  <i>({relative})</i>",
            f"   {_headline_summary(head)}",
        ]
        if head.get("url"):
            headline_block.append(f"   🔗 <a href=\"{_esc(head['url'])}\">Habere git</a>")
        headline_block.append("━━━━━━━━━━━━━━━━━━━━━━")

    # Sentiment etiketi (varsa)
    sentiment_line = ""
    sentiment = getattr(ev, "sentiment", None) or None
    if sentiment and sentiment.get("n", 0) >= 1:
        tone = sentiment.get("tone", "NEUTRAL")
        mean = sentiment.get("mean", 0)
        if tone == "NEGATIVE":
            sentiment_line = (
                f"⚠️ <b>HABER TONU NEGATIF</b> (skor: {mean:.1f}, "
                f"{sentiment['negative_n']}/{sentiment['n']} olumsuz baslik) "
                f"— dusus uyarisi"
            )
        elif tone == "POSITIVE":
            sentiment_line = (
                f"📈 <b>HABER TONU POZITIF</b> (skor: +{mean:.1f}, "
                f"{sentiment['positive_n']}/{sentiment['n']} olumlu baslik)"
            )

    lines = [
        f"{icon} <b>ONEMLI OLAY — {_esc(ev.ticker)}</b>",
        f"Sirket boyutu: <b>{_esc(cohort_tr)}</b>",
        f"Onem: <b>{_esc(severity_tr)}</b> | Skor: <b>{ev.composite}</b>",
        f"<b>{n_sources} farkli kaynak</b> ayni anda hareketlendi.",
    ]
    if sentiment_line:
        lines.append(sentiment_line)
    lines.extend(headline_block)
    lines.extend([
        "",
        "<b>📋 Tum sinyaller (detayli):</b>",
    ])

    for i, t in enumerate(ev.triggers[:6], 1):
        src_name = SOURCE_TR.get(t["source"], t["source"])
        z = t.get("z", 0) or 0
        mean = t.get("cohort_mean", 0) or 0
        std = t.get("cohort_std", 0) or 0
        cur = t.get("value", 0) or 0

        peak_age = t.get("peak_age_h", 0) or 0
        age_label = ""
        if peak_age >= 1:
            age_label = f" <i>({peak_age:.0f} saat once)</i>"
        elif peak_age > 0:
            age_label = f" <i>({int(peak_age*60)} dk once)</i>"
        lines.append(f"\n<b>{i}) {_esc(src_name)}</b>{age_label}")
        raw = t.get("raw_peak", cur)
        lines.append(f"   {_source_explanation(t['source'], raw, t.get('metadata') or {})}")

        # Z-score'u ratio'ya cevirip ac
        if mean > 0:
            lines.append(
                f"   📊 {_ratio_label(cur, mean)}  "
                f"<i>(istatistik: {_z_label(z)} z={z:.1f})</i>"
            )
        elif z > 0:
            lines.append(f"   📊 <i>{_z_label(z)} (z={z:.1f})</i>")

        if t.get("url"):
            lines.append(f"   🔗 <a href=\"{_esc(t['url'])}\">Detay</a>")

    lines.extend([
        "",
        f"📊 <a href=\"{DASHBOARD_URL}\">Dashboard'u ac</a>",
        "",
        "<i>Bu mesaj: birden fazla kaynak ayni anda olagandisi hareketlendi. "
        "Hisseyi acil incelemen onerilir.</i>",
    ])
    return "\n".join(lines)


def _send_one(token: str, chat_id: str, text: str) -> bool:
    try:
        payload = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        }).encode("utf-8")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            import json
            resp = json.loads(r.read())
        if not resp.get("ok"):
            LOG.error("Telegram API [%s]: %s", chat_id, resp)
            return False
        return True
    except Exception as exc:
        LOG.error("Telegram gonderim hatasi [%s]: %s", chat_id, exc)
        return False


def send_message(text: str, *, token: Optional[str] = None,
                 chat_id: Optional[str] = None) -> bool:
    """Tum chat_id'lere yollar. En az birine basariliysa True doner."""
    token = token or settings.TELEGRAM_BOT_TOKEN
    if not token:
        LOG.warning("Telegram token yok")
        return False

    if chat_id:
        ids = [chat_id]
    else:
        ids = settings.telegram_chat_ids
    if not ids:
        LOG.warning("Telegram chat_id yok")
        return False

    ok_any = False
    for cid in ids:
        if _send_one(token, cid, text):
            ok_any = True
    return ok_any


async def send_alpha_event(ev: AlphaEvent) -> bool:
    msg = format_message(ev)
    # urllib senkron - kisa mesaj icin asyncio.to_thread
    import asyncio
    return await asyncio.to_thread(send_message, msg)


async def send_startup_ping() -> bool:
    text = (
        "✅ <b>QuantAI Erken Uyari Motoru AKTIF</b>\n\n"
        "<b>Ne yapiyor?</b>\n"
        "Dakika basina su 4 kaynagi tarar:\n"
        "  • SEC resmi bildirimleri (8-K)\n"
        "  • Google News haber akisi\n"
        "  • Reddit yatirim forumlari\n"
        "  • Opsiyon piyasasi hareketleri\n\n"
        "<b>Ne zaman bildirim gelir?</b>\n"
        "Ayni hisse hakkinda <b>2 veya daha fazla kaynak</b> ayni anda "
        "olagandisi hareketlenirse (kohortuna gore) bu kanala uyari gelir.\n\n"
        "<b>Boyut kohortlari (skor stretching):</b>\n"
        "  • BUYUK ($200B+): NVDA, ASML, AVGO...\n"
        "  • ORTA ($10-200B): MU, ARM, SMCI...\n"
        "  • KUCUK (&lt;$10B): IONQ, AXTI, WOLF, RGTI...\n\n"
        "<b>Onem seviyeleri:</b>\n"
        "  🚨 <b>KRITIK</b> = SEC bildirimi VEYA 3+ kaynak ayni anda\n"
        "  ⚡ <b>YUKSEK</b> = 2 kaynak anomali\n\n"
        f"📊 <a href=\"{DASHBOARD_URL}\">Dashboard</a>"
    )
    import asyncio
    return await asyncio.to_thread(send_message, text)
