r"""
backtest_replay.py - Gecmis sinyallerden Alpha Engine performansini olc.

Ne yapar?
    1. signals.jsonl'daki TUM sinyalleri saatlik bucket'a koyup
       engine'i bastan sona yeniden oynatir (replay).
    2. Her tick'te ne event uretildigini kaydeder.
    3. Eger ticker icin gercek fiyat geçmisi varsa (yfinance), event'ten
       sonraki 24h/72h/7g fiyat hareketini olcer.
    4. Ozet rapor:
        - Event sayisi (KRITIK / YUKSEK)
        - Pozitif/negatif hit rate (event sonrasi %3+ hareket)
        - Source bazinda accuracy
        - "AXTI tarzi" yakalanmis vakalar

Calistirma:
    cd alpha_engine
    ..\venv\Scripts\python.exe backtest_replay.py
    ..\venv\Scripts\python.exe backtest_replay.py --ticker AXTI --days 30
    ..\venv\Scripts\python.exe backtest_replay.py --no-price (yfinance kullanma)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from config import setup_logging, settings  # noqa: E402

LOG = setup_logging()

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
SIGNALS_PATH = settings.STATE_DIR / "signals.jsonl"
HORIZONS_H = [24, 72, 24 * 7]  # 1 gun, 3 gun, 1 hafta
HIT_THRESHOLD = 0.03           # +%3 hareket "hit" sayilir


def _load_signals(path: Path, cutoff: Optional[datetime] = None) -> list[dict]:
    if not path.is_file():
        LOG.error("signals.jsonl bulunamadi: %s", path)
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_str = obj.get("timestamp")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if cutoff and ts < cutoff:
                continue
            obj["_ts"] = ts
            rows.append(obj)
    rows.sort(key=lambda x: x["_ts"])
    return rows


def _bucket_ticks(signals: list[dict], tick_minutes: int = 60) -> dict:
    """Sinyalleri tick basina grupla (saatlik default)."""
    buckets = defaultdict(list)
    for s in signals:
        ts = s["_ts"]
        floored = ts.replace(minute=0, second=0, microsecond=0)
        # Tick'i tick_minutes ile yuvarla
        if tick_minutes != 60:
            mins = (ts.minute // tick_minutes) * tick_minutes
            floored = ts.replace(minute=mins, second=0, microsecond=0)
        buckets[floored].append(s)
    return dict(sorted(buckets.items()))


async def _replay(signals: list[dict], ticker_filter: Optional[str] = None) -> list[dict]:
    """
    Sinyalleri sirasiyla engine'e besler, her tick'te uretilen event'leri toplar.
    """
    # Engine singleton + bus'i temp dir'e yonlendir (canli state korunsun)
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="backtest_"))
    LOG.info("Backtest temp dir: %s", tmp)

    # Bus'i gecici dosyaya bagla
    from collections import defaultdict
    from src.common import signal_bus as sb_module
    sb_module._bus_singleton = None  # singleton sifirla
    from src.common.signal_bus import Signal, SignalBus, get_signal_bus
    bus = SignalBus(tmp / "signals.jsonl", max_age_h=24 * 30)
    sb_module._bus_singleton = bus

    # Engine singleton'i sifirla, bagimsiz instance olustur
    from src.analytics import engine as eng_module
    eng_module._engine_singleton = None
    from src.analytics.engine import CompositeAlphaEngine
    engine = CompositeAlphaEngine()
    # State'i temp'e ayir
    engine.state_dir = tmp
    engine.cohort_path = tmp / "cohort_map.json"
    engine.baseline_path = tmp / "cohort_baseline.json"
    engine.baseline = defaultdict(list)

    # Gercek cohort haritasini kopya al (yfinance cagrisini onlemek icin)
    real_cohort = settings.STATE_DIR / "cohort_map.json"
    if real_cohort.is_file():
        try:
            data = json.loads(real_cohort.read_text(encoding="utf-8"))
            cohorts = data.get("cohorts", data)
            engine.cohort_map = {k.upper(): v for k, v in cohorts.items()}
            caps = data.get("caps", {})
            engine.market_caps = {k.upper(): float(v) for k, v in caps.items()}
            import time
            engine._last_cohort_refresh = time.time()
        except Exception:
            pass

    buckets = _bucket_ticks(signals, tick_minutes=60)
    LOG.info("Backtest: %d sinyal -> %d tick", len(signals), len(buckets))

    detected = []
    for tick_ts, batch in buckets.items():
        # Filtre uygulanabilir
        if ticker_filter:
            batch = [s for s in batch if s.get("ticker", "").upper() == ticker_filter]
            if not batch:
                continue
        # Sinyalleri bus'a emit et
        for s in batch:
            try:
                sig = Signal(
                    source=s.get("source", ""),
                    ticker=(s.get("ticker") or "").upper(),
                    value=float(s.get("value", 0) or 0),
                    timestamp=s["_ts"],
                    metadata=s.get("metadata") or {},
                    url=s.get("url"),
                    event_id=s.get("event_id"),
                )
                await bus.emit(sig)
            except Exception:
                continue

        # Bu tick icin engine'i calistir
        try:
            events = await engine.update_and_detect(window_h=72.0)
        except Exception as exc:
            LOG.warning("tick %s engine err: %s", tick_ts, exc)
            continue
        for ev in events:
            if ticker_filter and ev.ticker != ticker_filter:
                continue
            detected.append({
                "tick": tick_ts,
                "ticker": ev.ticker,
                "severity": ev.severity,
                "composite": ev.composite,
                "cohort": ev.cohort,
                "n_sources": len(ev.triggers),
                "sources": sorted({t["source"] for t in ev.triggers}),
                "headline": ev.headline,
                "sentiment": ev.sentiment.get("tone") if ev.sentiment else None,
            })
    return detected


def _measure_price_impact(events: list[dict],
                            no_price: bool = False) -> dict:
    """Each event icin event tarihinden sonraki fiyat hareketi (yfinance)."""
    if no_price:
        return {}
    try:
        import yfinance as yf
    except ImportError:
        LOG.warning("yfinance yok, fiyat olcumu atlandi")
        return {}

    tickers = sorted({e["ticker"] for e in events})
    if not tickers:
        return {}
    LOG.info("Fiyat verisi cekiliyor: %d ticker", len(tickers))

    # Tum tickerlari bir kerede cek (30 gun)
    histories = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="60d", interval="1d")
            if hist.empty:
                continue
            histories[ticker] = hist
        except Exception as exc:
            LOG.warning("yfinance %s: %s", ticker, str(exc)[:80])

    impacts = []
    for ev in events:
        hist = histories.get(ev["ticker"])
        if hist is None or hist.empty:
            continue
        event_date = ev["tick"]
        # Event gunundeki kapanis fiyati (en yakin tarih)
        try:
            idx = hist.index.tz_convert("UTC") if hist.index.tz is not None else hist.index.tz_localize("UTC")
            hist = hist.copy()
            hist.index = idx
        except Exception:
            pass
        try:
            cutoff = event_date
            before = hist[hist.index <= cutoff]
            if before.empty:
                continue
            anchor_price = float(before["Close"].iloc[-1])
            anchor_date = before.index[-1]
            move_pct = {}
            for h in HORIZONS_H:
                target = anchor_date + timedelta(hours=h)
                after = hist[hist.index >= target]
                if after.empty:
                    move_pct[h] = None
                else:
                    px = float(after["Close"].iloc[0])
                    move_pct[h] = round((px - anchor_price) / anchor_price * 100, 2)
            impacts.append({
                **ev,
                "anchor_price": round(anchor_price, 2),
                "move_24h": move_pct[24],
                "move_72h": move_pct[72],
                "move_7d": move_pct[24 * 7],
            })
        except Exception as exc:
            LOG.debug("price impact %s: %s", ev["ticker"], exc)

    if not impacts:
        return {}

    # Aggregate
    total = len(impacts)
    hit_24h = sum(1 for i in impacts if i["move_24h"] is not None
                   and abs(i["move_24h"]) >= HIT_THRESHOLD * 100)
    hit_72h = sum(1 for i in impacts if i["move_72h"] is not None
                   and abs(i["move_72h"]) >= HIT_THRESHOLD * 100)
    pos_24h = sum(1 for i in impacts if i["move_24h"] is not None and i["move_24h"] >= 3)
    neg_24h = sum(1 for i in impacts if i["move_24h"] is not None and i["move_24h"] <= -3)

    return {
        "impacts": impacts,
        "total": total,
        "hit_24h_pct": round(100 * hit_24h / total, 1) if total else 0,
        "hit_72h_pct": round(100 * hit_72h / total, 1) if total else 0,
        "positive_24h": pos_24h,
        "negative_24h": neg_24h,
    }


def _dedupe_events(events: list[dict], cooldown_hours: int = 24) -> list[dict]:
    """Ayni (ticker, source_set) icin cooldown_hours icinde tek event tut.
    En erken detection zamanini koru.
    """
    seen: dict[tuple, datetime] = {}
    unique = []
    for ev in sorted(events, key=lambda e: e["tick"]):
        key = (ev["ticker"], tuple(sorted(ev["sources"])))
        last = seen.get(key)
        if last and (ev["tick"] - last).total_seconds() < cooldown_hours * 3600:
            continue
        seen[key] = ev["tick"]
        unique.append(ev)
    return unique


def _report(events: list[dict], impact: dict, raw_count: int = 0) -> None:
    print("\n" + "=" * 72)
    print(f"  BACKTEST RAPORU - {len(events)} UNIQUE EVENT (ham: {raw_count})")
    print("=" * 72)
    if not events:
        print("Hic event yok. Daha eski tarihlere bak (--days 30).")
        return

    sev_counts = Counter(e["severity"] for e in events)
    print(f"\nOnem dagilimi:")
    print(f"  KRITIK: {sev_counts.get('KRITIK', 0)}")
    print(f"  YUKSEK: {sev_counts.get('YUKSEK', 0)}")

    # Ticker bazinda
    by_ticker = Counter(e["ticker"] for e in events)
    print(f"\nEn cok event uretilen 10 ticker:")
    for t, c in by_ticker.most_common(10):
        print(f"  {t:8s} {c} event")

    # Source bazinda
    src = Counter()
    for e in events:
        for s in e["sources"]:
            src[s] += 1
    print(f"\nKaynak kullanim sayisi:")
    for s, c in src.most_common():
        print(f"  {s:20s} {c}")

    if impact:
        n_with_24h = sum(1 for i in impact["impacts"] if i.get("move_24h") is not None)
        n_with_72h = sum(1 for i in impact["impacts"] if i.get("move_72h") is not None)
        print(f"\n{'-' * 72}")
        print(f"FIYAT ETKISI ({impact['total']} event icin yfinance ile)")
        print(f"{'-' * 72}")
        if n_with_24h == 0:
            now = datetime.now(timezone.utc)
            recent = sum(1 for i in impact["impacts"]
                          if (now - i["tick"]).total_seconds() < 24 * 3600)
            print(f"  ! Henuz hicbir event'in 24h fiyat verisi yok.")
            print(f"    Event'lerin {recent}/{impact['total']} adedi son 24 saat icinde.")
            print(f"    Engine yakinda yeni veri toplayacak; --days 7 ile yarin tekrar dene.")
            return
        print(f"  24h verisi olan: {n_with_24h}/{impact['total']}, "
              f"72h verisi olan: {n_with_72h}/{impact['total']}")
        print(f"  24h sonra >= ±3% hareket: {impact['hit_24h_pct']}% "
              f"({impact['positive_24h']} +, {impact['negative_24h']} -)")
        print(f"  72h sonra >= ±3% hareket: {impact['hit_72h_pct']}%")

        print(f"\nEN BUYUK HAREKETLER (24h sonra):")
        sorted_imp = sorted(
            [i for i in impact["impacts"] if i.get("move_24h") is not None],
            key=lambda x: -abs(x["move_24h"]),
        )[:10]
        for imp in sorted_imp:
            move = imp["move_24h"]
            arrow = "UP  " if move > 0 else "DOWN"
            print(f"  {arrow} {imp['ticker']:6s} {move:+6.2f}%  "
                  f"{imp['severity']:6s}  "
                  f"{imp['tick'].strftime('%d %b %H:%M')}  "
                  f"{imp['headline'][:50]}")


async def main_async() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14,
                    help="Geriye dogru kac gun (default 14)")
    ap.add_argument("--ticker", type=str, default=None,
                    help="Tek bir ticker'a filtrele (TUMU)")
    ap.add_argument("--no-price", action="store_true",
                    help="Yfinance fiyat olcumu yapma")
    ap.add_argument("--out", type=str, default=None,
                    help="JSON cikti dosyasi (rapor + tum event'ler)")
    args = ap.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    signals = _load_signals(SIGNALS_PATH, cutoff=cutoff)
    if not signals:
        print("Hic sinyal bulunamadi.")
        return 1

    LOG.info("Backtest: %d sinyal yuklendi (son %d gun)", len(signals), args.days)
    ticker_filter = args.ticker.upper() if args.ticker else None
    all_events = await _replay(signals, ticker_filter=ticker_filter)
    raw_count = len(all_events)
    events = _dedupe_events(all_events, cooldown_hours=24)
    impact = _measure_price_impact(events, no_price=args.no_price)
    _report(events, impact, raw_count=raw_count)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(json.dumps({
            "events": [
                {**e, "tick": e["tick"].isoformat()}
                for e in events
            ],
            "impact_summary": {
                k: v for k, v in impact.items() if k != "impacts"
            },
        }, indent=2, default=str), encoding="utf-8")
        print(f"\nCikti yazildi: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
