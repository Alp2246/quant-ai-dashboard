"""
phone_app_server.py - PWA static dosya sunucusu (port 8502).

Mimari:
    [Telefon] ---http://192.168.1.X:8502---> PWA Shell (index.html + SW + manifest + icons)
                                                    |
                                                    | <iframe>
                                                    v
    [Telefon] ---http://192.168.1.X:8501---> Streamlit Dashboard (gercek uygulama)

Avantajlari:
  - PWA shell sayesinde telefonun "Ana ekrana ekle" cikar -> app gibi durur
  - PWABuilder.com bu URL'yi APK'ya cevirebilir
  - service-worker offline destek + push notification altyapisi saglar

Bagimlilik: Sadece Python stdlib (http.server, socketserver, threading).
"""
from __future__ import annotations

import logging
import os
import socket
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

LOG = logging.getLogger("phone_app_server")
DEFAULT_PORT = 8502


def _phone_app_dir() -> Path:
    """phone_app/ klasorunu bul (PyInstaller bundle veya dev mode)."""
    if hasattr(sys, "_MEIPASS"):
        bundle = Path(sys._MEIPASS)
        candidate = bundle / "phone_app"
        if candidate.is_dir():
            return candidate
    here = Path(__file__).parent
    return here / "phone_app"


PWA_ROOT = _phone_app_dir()


_EXTRA_MIME = {
    ".webmanifest": "application/manifest+json",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


class _PWAHandler(SimpleHTTPRequestHandler):
    """HTTP handler — phone_app/ klasorunu serve eder, dogru MIME ile."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PWA_ROOT), **kwargs)

    def guess_type(self, path):  # type: ignore[override]
        ext = os.path.splitext(path)[1].lower()
        if ext in _EXTRA_MIME:
            return _EXTRA_MIME[ext]
        return super().guess_type(path)

    def end_headers(self):  # type: ignore[override]
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-cache, max-age=0, must-revalidate")
        self.send_header("Service-Worker-Allowed", "/")
        super().end_headers()

    def do_GET(self):  # type: ignore[override]
        if self.path in ("", "/"):
            self.path = "/index.html"
        if self.path == "/health":
            self._send_json({"status": "ok", "pwa_root": str(PWA_ROOT)})
            return
        super().do_GET()

    def _send_json(self, payload: dict) -> None:
        import json
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # type: ignore[override]
        LOG.debug("%s - %s", self.address_string(), format % args)


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def serve(port: int = DEFAULT_PORT, *, daemon: bool = True) -> threading.Thread:
    """PWA sunucuyu arka planda baslat, thread dondur."""
    if not PWA_ROOT.is_dir():
        LOG.error("phone_app/ klasoru bulunamadi: %s", PWA_ROOT)
        raise FileNotFoundError(f"phone_app dir missing: {PWA_ROOT}")

    httpd = ThreadingHTTPServer(("0.0.0.0", port), _PWAHandler)

    def _run():
        try:
            LOG.info("PWA server dinliyor: http://0.0.0.0:%d (root=%s)", port, PWA_ROOT)
            httpd.serve_forever()
        except Exception as e:
            LOG.error("PWA server hatasi: %s", e)
        finally:
            httpd.server_close()

    t = threading.Thread(target=_run, name="phone-app-server", daemon=daemon)
    t.start()
    return t


def banner_lines(port: int = DEFAULT_PORT) -> list[str]:
    """launcher.py'in banner'a ekleyecegi satirlar."""
    ip = _local_ip()
    return [
        f"    Telefon APP (PWA):    http://{ip}:{port}",
        f"    Telefonda 'Ana Ekrana Ekle' -> app gibi acilir",
    ]


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    import argparse
    p = argparse.ArgumentParser(description="Quant AI Dashboard PWA shell server")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--standalone", action="store_true", help="Foreground (block) modunda calistir")
    args = p.parse_args(argv)

    ip = _local_ip()
    print(f"\n[Quant AI PWA Shell]")
    print(f"  Root        : {PWA_ROOT}")
    print(f"  Bilgisayar  : http://localhost:{args.port}")
    print(f"  Telefon (LAN): http://{ip}:{args.port}")
    print(f"  Health      : http://localhost:{args.port}/health")
    print(f"\n  Ctrl+C ile durdur\n")

    if args.standalone:
        try:
            httpd = ThreadingHTTPServer(("0.0.0.0", args.port), _PWAHandler)
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDurduruldu.")
            return 0
    else:
        t = serve(args.port, daemon=False)
        t.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
