"""
phone_app_server.py - Gateway (port 8502).

- /.well-known/assetlinks.json  -> Android TWA dogrulama (APK beyaz ekran fix)
- Diger tum istekler            -> Streamlit (127.0.0.1:8501)

Tailscale Funnel bu porta (8502) baglanir; telefon/APK tam dashboard gorur.
"""
from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

LOG = logging.getLogger("phone_app_server")
DEFAULT_PORT = 8502
STREAMLIT_PORT = 8501


def _project_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.resolve()


PROJECT_ROOT = _project_root()
ASSETLINKS = PROJECT_ROOT / "static" / ".well-known" / "assetlinks.json"
STREAMLIT_BASE = f"http://127.0.0.1:{STREAMLIT_PORT}"


class _GatewayHandler(BaseHTTPRequestHandler):
    """TWA assetlinks + Streamlit reverse proxy."""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        LOG.debug("%s - %s", self.address_string(), fmt % args)

    def do_GET(self):
        self._handle()

    def do_HEAD(self):
        self._handle(head_only=True)

    def do_POST(self):
        self._handle()

    def _handle(self, *, head_only: bool = False) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/.well-known/assetlinks.json", "/.well-known/assetlinks.json/"):
            self._serve_assetlinks(head_only=head_only)
            return
        if path == "/health":
            self._send_json({"status": "ok", "gateway": True, "streamlit": STREAMLIT_BASE})
            return
        self._proxy_to_streamlit(head_only=head_only)

    def _serve_assetlinks(self, *, head_only: bool = False) -> None:
        if not ASSETLINKS.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "assetlinks.json missing")
            return
        body = ASSETLINKS.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _proxy_to_streamlit(self, *, head_only: bool = False) -> None:
        url = STREAMLIT_BASE + self.path
        try:
            body = None
            if self.command in ("POST", "PUT", "PATCH"):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else None
            req = urllib.request.Request(
                url,
                data=body,
                method=self.command,
                headers={k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection")},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    lk = k.lower()
                    if lk not in ("transfer-encoding", "connection"):
                        self.send_header(k, v)
                self.end_headers()
                if not head_only and self.command != "HEAD":
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.end_headers()
            if not head_only:
                self.wfile.write(e.read())
        except Exception as e:
            LOG.error("Proxy error %s: %s", url, e)
            self.send_error(HTTPStatus.BAD_GATEWAY, str(e))

    def _send_json(self, payload: dict) -> None:
        import json
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def serve(port: int = DEFAULT_PORT, *, daemon: bool = True) -> threading.Thread:
    if not ASSETLINKS.is_file():
        LOG.warning("assetlinks.json yok: %s (APK beyaz ekran riski)", ASSETLINKS)

    httpd = ThreadingHTTPServer(("0.0.0.0", port), _GatewayHandler)

    def _run():
        LOG.info("Gateway :8502 -> Streamlit :8501 + assetlinks")
        try:
            httpd.serve_forever()
        except Exception as e:
            LOG.error("Gateway error: %s", e)
        finally:
            httpd.server_close()

    t = threading.Thread(target=_run, name="quant-gateway", daemon=daemon)
    t.start()
    return t


def banner_lines(port: int = DEFAULT_PORT) -> list[str]:
    ip = _local_ip()
    return [
        f"    Telefon / APK (Funnel): https://abozer.tail4ea368.ts.net",
        f"    LAN gateway            : http://{ip}:{port}",
    ]


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    import argparse
    p = argparse.ArgumentParser(description="Quant AI Gateway (assetlinks + Streamlit proxy)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = p.parse_args(argv)
    print(f"Gateway http://0.0.0.0:{args.port} -> Streamlit {STREAMLIT_BASE}")
    httpd = ThreadingHTTPServer(("0.0.0.0", args.port), _GatewayHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
