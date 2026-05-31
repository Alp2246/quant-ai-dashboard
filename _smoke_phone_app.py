"""Smoke test: PWA server + launcher integration."""
from __future__ import annotations
import sys
import threading
import time
import urllib.request


def test_pwa_server() -> None:
    from phone_app_server import serve, PWA_ROOT
    assert PWA_ROOT.is_dir(), f"missing {PWA_ROOT}"
    serve(18502, daemon=True)
    time.sleep(0.8)
    for path in ("/health", "/", "/manifest.webmanifest", "/icons/icon-192.png"):
        url = f"http://127.0.0.1:18502{path}"
        r = urllib.request.urlopen(url, timeout=5)
        assert r.status == 200, f"{path} -> {r.status}"
    print("  PWA server: OK")


def test_launcher_import() -> None:
    import launcher
    assert launcher.PORT == 8501
    assert launcher.PWA_PORT == 8502
    print("  launcher constants: OK")


def main() -> int:
    print("phone_app smoke test")
    test_launcher_import()
    test_pwa_server()
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
