"""Capture Erken Uyari tab only."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"

with sync_playwright() as p:
    page = p.chromium.launch(headless=True).new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://127.0.0.1:8501", wait_until="domcontentloaded")
    page.wait_for_timeout(15_000)
    page.locator('button[data-baseweb="tab"]').filter(has_text="Erken").first.click()
    page.wait_for_timeout(5_000)
    page.screenshot(path=str(OUT / "03-alpha-engine.png"), full_page=True)
    print("OK 03-alpha-engine.png")
