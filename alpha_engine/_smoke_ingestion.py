"""Adim 2 entegrasyon smoke test."""
from __future__ import annotations
import asyncio
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")  # config + src import edebilelim
from config import settings, setup_logging  # noqa: E402

LOG = setup_logging()


async def _section(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


async def main() -> int:
    from main import TaskContext  # noqa: E402
    from src.common.signal_bus import get_signal_bus  # noqa: E402
    from src.common.http_client import get_http_client  # noqa: E402

    # --- 1. SignalBus basit testi (her seferinde unique ID kullanarak) ---
    await _section("1) SignalBus emit + dedup")
    bus = get_signal_bus()
    from src.common.signal_bus import Signal
    test_id = f"smoke-{int(datetime.now(timezone.utc).timestamp())}"
    s1 = Signal(source="test", ticker="AXTI", value=1.0,
                metadata={"x": 1}, event_id=test_id)
    s2 = Signal(source="test", ticker="AXTI", value=1.0,
                metadata={"x": 1}, event_id=test_id)
    ok1 = await bus.emit(s1)
    ok2 = await bus.emit(s2)
    print(f"  ilk emit:    {ok1}  (True olmali)")
    print(f"  ikinci emit: {ok2}  (False olmali - dedup)")
    assert ok1 is True and ok2 is False, "FAIL signal bus dedup"
    print("  dedup OK")

    # --- 2. SEC EDGAR canli test (1 tick) ---
    await _section("2) SECScanner canli poll (gercek SEC EDGAR HTTP)")
    if settings.sec_enabled:
        from src.ingestion.sec_edgar import poll as sec_poll
        ctx = TaskContext(tick_id=1, tick_started_at=datetime.now(timezone.utc))
        try:
            await asyncio.wait_for(sec_poll(ctx), timeout=120)
            print("  SECScanner: OK")
        except Exception as exc:
            print(f"  SECScanner: ERR {exc}")
        # Sec signal'larini say
        sec_signals = await bus.recent(source="sec_edgar", lookback_h=24)
        print(f"  toplam sec_edgar sinyali (24h): {len(sec_signals)}")
        if sec_signals:
            sample = sec_signals[0]
            print(f"  ornek: {sample.ticker} -> {sample.metadata.get('title')[:80]}")
            print(f"          url: {sample.url}")
    else:
        print("  SEC DISABLED - skipped")

    # --- 3. Reddit canli test (eger yapilandirilmissa) ---
    await _section("3) RedditScanner")
    if settings.reddit_enabled:
        from src.ingestion.reddit import poll as reddit_poll
        ctx = TaskContext(tick_id=2, tick_started_at=datetime.now(timezone.utc))
        try:
            await asyncio.wait_for(reddit_poll(ctx), timeout=90)
            print("  RedditScanner: OK")
        except Exception as exc:
            print(f"  RedditScanner: ERR {exc}")
        reddit_signals = await bus.recent(source="reddit", lookback_h=1)
        print(f"  son 1h reddit sinyali: {len(reddit_signals)}")
        for s in reddit_signals[:5]:
            print(f"    {s.ticker}: {int(s.value)} mention")
    else:
        print("  REDDIT DISABLED - skipped (REDDIT_CLIENT_ID/SECRET eksik)")

    # --- 4. Polygon ---
    await _section("4) PolygonOptionsScanner")
    if settings.polygon_enabled:
        from src.ingestion.polygon_options import poll as poly_poll
        ctx = TaskContext(tick_id=3, tick_started_at=datetime.now(timezone.utc))
        try:
            await asyncio.wait_for(poly_poll(ctx), timeout=60)
            print("  PolygonScanner: OK")
        except Exception as exc:
            print(f"  PolygonScanner: ERR {exc}")
    else:
        print("  POLYGON DISABLED - skipped")

    # --- 5. SignalBus genel ozet ---
    await _section("5) SignalBus ozet")
    all_signals = await bus.recent(lookback_h=24)
    by_source = {}
    for s in all_signals:
        by_source[s.source] = by_source.get(s.source, 0) + 1
    print(f"  toplam aktif sinyal (24h): {len(all_signals)}")
    for src, n in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"    {src:20s}: {n}")

    # --- 6. SEC EDGAR ikinci tick: dedup dogrulamasi ---
    if settings.sec_enabled:
        await _section("6) SEC EDGAR 2. tick - dedup dogrulamasi")
        before = len([s for s in await bus.recent(source="sec_edgar", lookback_h=24)])
        from src.ingestion.sec_edgar import poll as sec_poll
        ctx = TaskContext(tick_id=99, tick_started_at=datetime.now(timezone.utc))
        await asyncio.wait_for(sec_poll(ctx), timeout=120)
        after = len([s for s in await bus.recent(source="sec_edgar", lookback_h=24)])
        delta = after - before
        print(f"  ikinci poll sonrasi yeni sinyal: {delta}")
        print(f"  (0 olmali - hepsi dedup'lanmali)")
        assert delta == 0, f"FAIL: dedup calismadi, +{delta}"

    print("\nSmoke test tamam.")
    # HTTP client + reddit temizle
    client = get_http_client()
    await client.aclose()
    if settings.reddit_enabled:
        try:
            from src.ingestion.reddit import _get_singleton as _rs
            await _rs().aclose()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
