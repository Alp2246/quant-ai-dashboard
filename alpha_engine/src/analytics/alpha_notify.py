"""
alpha_notify - tick sonu: ALPHA EVENT tespit + Telegram push.
"""
from __future__ import annotations

import logging

from config import settings
from src.analytics.engine import (
    detect_alpha_events,
    filter_with_cooldown,
    get_engine,
)
from src.notifiers.telegram_push import send_alpha_event, send_startup_ping

LOG = logging.getLogger(__name__)
_startup_sent = False


async def poll(ctx) -> None:
    global _startup_sent
    if not settings.telegram_enabled:
        LOG.warning("Telegram kapali - uyari gonderilmez")
        return

    if not _startup_sent and ctx.tick_id <= 1:
        ok = await send_startup_ping()
        if ok:
            _startup_sent = True
            LOG.info("Telegram baslangic mesaji gonderildi")
        try:
            snap = get_engine().snapshot()
            LOG.info("[engine snapshot] %s", snap.get("cohort_counts"))
        except Exception:
            pass

    events = await detect_alpha_events()
    if not events:
        LOG.debug("[alpha_notify] olay yok")
        return

    to_send = await filter_with_cooldown(events)
    if not to_send:
        LOG.info("[alpha_notify] %d olay bulundu ama cooldown'da", len(events))
        return

    sent = 0
    for ev in to_send[:5]:  # tick basina max 5 mesaj (spam onleme)
        ok = await send_alpha_event(ev)
        if ok:
            sent += 1
            LOG.info("[alpha_notify] Telegram OK %s %s skor=%.1f",
                     ev.ticker, ev.severity, ev.composite)
        else:
            LOG.error("[alpha_notify] Telegram FAIL %s", ev.ticker)

    LOG.info("[alpha_notify] %d/%d uyari gonderildi", sent, len(to_send))
