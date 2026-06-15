"""Tek test mesaji Telegram'a gonder."""
from __future__ import annotations
import asyncio
import sys

sys.path.insert(0, ".")

from src.analytics.engine import AlphaEvent
from src.notifiers.telegram_push import send_alpha_event, send_startup_ping


async def main() -> int:
    print("1) Baslangic mesaji...")
    ok1 = await send_startup_ping()
    print("   ", "OK" if ok1 else "FAIL")

    print("2) Ornek ONEMLI OLAY (AXTI)...")
    ev = AlphaEvent(
        ticker="AXTI",
        composite=14.1,
        severity="KRITIK",
        cohort="SMALL",
        triggers=[
            {
                "source": "reddit_rss",
                "label": "Reddit",
                "z": 7.98,
                "value": 10.0,
                "cohort_mean": 1.16,
                "cohort_std": 1.11,
                "detail": "10 mention (1s)",
                "url": "https://www.reddit.com/search/?q=%24AXTI&sort=new",
                "metadata": {},
            },
            {
                "source": "google_news",
                "label": "Haber",
                "z": 4.2,
                "value": 6.0,
                "cohort_mean": 1.0,
                "cohort_std": 1.2,
                "detail": "AXT Inc gallium export ban (TEST)",
                "url": "https://news.google.com/search?q=AXT+gallium+export",
                "metadata": {
                    "latest_title": "AXT Inc gallium export ban (TEST)",
                },
            },
            {
                "source": "sec_edgar",
                "label": "SEC 8-K",
                "z": 3.1,
                "value": 1.0,
                "cohort_mean": 0.2,
                "cohort_std": 0.4,
                "detail": "8-K - Material event (TEST)",
                "url": "https://www.sec.gov/Archives/edgar/data/895456/test",
                "metadata": {"title": "8-K - Material event (TEST)"},
            },
        ],
        headline="Test: onemli olay simulasyonu",
    )
    ok2 = await send_alpha_event(ev)
    print("   ", "OK" if ok2 else "FAIL")
    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
