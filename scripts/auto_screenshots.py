"""
Capture Streamlit dashboard screenshots for GitHub (requires playwright).

  pip install playwright
  playwright install chromium
  python scripts/auto_screenshots.py

Ensure dashboard is running: paylasim_baslat.bat or run.bat
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
BASE = "http://127.0.0.1:8501"

# Streamlit main tabs (app.py) — Investor Summary is ABOVE tabs (full-page shot)
TABS = [
    ("01-dashboard-overview.png", None),  # full page: Investor Summary + top
    ("03-alpha-engine.png", "Erken Uyari"),
    ("02-investor-summary.png", None),  # scroll to top section duplicate ok
    ("04-detail-analysis.png", "Detay"),
]


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install: venv\\Scripts\\pip install playwright")
        print("Then:    venv\\Scripts\\playwright install chromium")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Output: {OUT}")
    print("Waiting for Streamlit (up to 120s)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(120_000)

        page.goto(BASE, wait_until="domcontentloaded")
        print("Initial load — waiting 90s for Master Score...")
        page.wait_for_timeout(90_000)

        page.screenshot(path=str(OUT / "01-dashboard-overview.png"), full_page=True)
        print("  OK 01-dashboard-overview.png (Investor Summary + header)")

        # Investor summary is in first viewport — also save viewport crop
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1_000)
        page.screenshot(path=str(OUT / "02-investor-summary.png"), full_page=False)
        print("  OK 02-investor-summary.png")

        for filename, tab_label in TABS[2:]:
            if not tab_label:
                continue
            try:
                loc = page.get_by_role("tab", name=tab_label)
                if loc.count() == 0:
                    loc = page.locator('button[data-baseweb="tab"]').filter(
                        has_text=tab_label.replace("Erken Uyari", "Erken").replace("Detay", "Detay")
                    )
                loc.first.click(timeout=20_000)
                page.wait_for_timeout(6_000)
                page.screenshot(path=str(OUT / filename), full_page=True)
                print(f"  OK {filename}")
            except Exception as exc:
                print(f"  SKIP {filename}: {exc}")

        # Social preview crop (1280x640 center top)
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_timeout(5_000)
        page.screenshot(path=str(OUT / "github-social-preview.png"), full_page=False)
        print("  OK github-social-preview.png")

        browser.close()

    print("Done. Commit: git add docs/screenshots && git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
