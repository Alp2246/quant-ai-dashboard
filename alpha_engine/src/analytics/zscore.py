"""
zscore - kaynak bazli rolling z-score.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable

from src.common.signal_bus import Signal


def _hour_bucket(ts: datetime) -> datetime:
    return ts.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


def compute_zscores(
    signals: Iterable[Signal],
    *,
    current_window_h: float = 1.0,
    baseline_window_h: float = 72.0,
    min_samples: int = 3,
) -> dict[str, dict[str, dict]]:
    """
  Returns: { ticker: { source: { z, current, mean, std, n_baseline, latest_meta, url } } }
    """
    now = datetime.now(timezone.utc)
    cur_cut = now - timedelta(hours=current_window_h)
    base_start = now - timedelta(hours=baseline_window_h)
    base_end = cur_cut

    # hourly aggregates for baseline
    hourly: dict[tuple[str, str], dict[datetime, float]] = defaultdict(lambda: defaultdict(float))
    current: dict[tuple[str, str], float] = defaultdict(float)
    latest: dict[tuple[str, str], Signal] = {}

    for s in signals:
        ts = s.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        key = (s.ticker.upper(), s.source)
        if ts >= cur_cut:
            current[key] += float(s.value)
            if key not in latest or ts > latest[key].timestamp:
                latest[key] = s
        elif base_start <= ts < base_end:
            hb = _hour_bucket(ts)
            hourly[key][hb] += float(s.value)

    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for (ticker, source), cur_val in current.items():
        if cur_val <= 0:
            continue
        buckets = list(hourly.get((ticker, source), {}).values())
        if len(buckets) < min_samples:
            # Yetersiz tarih: std=0 -> z yok, absolute rules devreye girer
            mean, std = 0.0, 0.0
            z = 0.0
        else:
            mean = sum(buckets) / len(buckets)
            var = sum((x - mean) ** 2 for x in buckets) / max(1, len(buckets) - 1)
            std = math.sqrt(var) if var > 0 else 0.0
            z = (cur_val - mean) / std if std > 1e-6 else (3.0 if cur_val > mean else 0.0)

        sig = latest.get((ticker, source))
        out[ticker][source] = {
            "z": round(z, 2),
            "current": round(cur_val, 2),
            "mean": round(mean, 2),
            "std": round(std, 2),
            "n_baseline": len(buckets),
            "metadata": sig.metadata if sig else {},
            "url": sig.url if sig else None,
            "timestamp": sig.timestamp.isoformat() if sig else None,
        }
    return dict(out)
