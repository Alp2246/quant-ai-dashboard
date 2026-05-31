"""Tunnel uzerinden PWA shell erisimini test et."""
import urllib.request
import sys

URL = "https://kansas-charitable-houston-symposium.trycloudflare.com"

def check(path):
    full = URL + path
    try:
        r = urllib.request.urlopen(full, timeout=10)
        return r.status, r.headers.get("Content-Type", ""), len(r.read(8192))
    except Exception as e:
        return None, str(e), 0

for path in ("/health", "/manifest.webmanifest", "/service-worker.js", "/icons/icon-192.png"):
    status, ct, n = check(path)
    print(f"  {status}  {n:>6}  {ct[:40]:<40}  {path}")
