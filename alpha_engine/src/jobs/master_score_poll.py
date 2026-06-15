"""
master_score_poll - Alpha Engine icinde periyodik Master Score + Telegram.

Her MASTER_SCORE_INTERVAL_MIN dakikada bir score_job calistirir.
Streamlit gerekmez.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from config import settings

LOG = logging.getLogger(__name__)
_last_run_tick = -999_999


async def poll(ctx) -> None:
    global _last_run_tick
    # 4 saatte bir (240 dk); tick=60s -> 240 tick
    interval_min = int(getattr(settings, "MASTER_SCORE_INTERVAL_MIN", 240) or 240)
    ticks_per_run = max(60, int(interval_min * 60 / max(5, settings.TICK_SECONDS)))

    if ctx.tick_id - _last_run_tick < ticks_per_run:
        return

    if not settings.telegram_enabled:
        return

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import asyncio
    import os
    import subprocess

    LOG.info("[master_score] cekirdek skor taramasi basliyor (tick=%d)", ctx.tick_id)
    py = root / "venv" / "bin" / "python"
    script = root / "score_job.py"
    env = {
        **os.environ,
        "PYTHONPATH": str(root),
        "HOME": str(root),
        "XDG_CACHE_HOME": str(root / ".cache"),
        "NLTK_DATA": str(root / ".cache" / "nltk_data"),
    }

    def _run_subprocess():
        return subprocess.run(
            [str(py), str(script)],
            cwd=str(root),
            env=env,
            timeout=3600,
            capture_output=True,
            text=True,
        )

    try:
        proc = await asyncio.to_thread(_run_subprocess)
        if proc.returncode != 0:
            LOG.error("[master_score] exit=%s stderr=%s",
                      proc.returncode, (proc.stderr or "")[-500:])
        else:
            LOG.info("[master_score] tamamlandi")
    except Exception as exc:
        LOG.error("[master_score] hata: %s", exc)
    finally:
        _last_run_tick = ctx.tick_id
