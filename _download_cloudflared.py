"""Download cloudflared.exe (~20 MB) for APK helper."""
import os
import sys
import urllib.request
from pathlib import Path

TARGET = Path("tools/cloudflared.exe")
URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

TARGET.parent.mkdir(parents=True, exist_ok=True)

if TARGET.exists() and TARGET.stat().st_size > 1_000_000:
    print(f"OK zaten var: {TARGET} ({TARGET.stat().st_size / 1024 / 1024:.1f} MB)")
    sys.exit(0)

print(f"Indiriliyor: {URL}")
print(f"Hedef       : {TARGET.resolve()}")

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=120) as r:
    total = int(r.headers.get("Content-Length", "0"))
    print(f"Boyut       : {total / 1024 / 1024:.1f} MB")
    data = bytearray()
    chunk = 64 * 1024
    while True:
        b = r.read(chunk)
        if not b:
            break
        data.extend(b)
        if total:
            pct = len(data) * 100 // total
            if pct % 10 == 0:
                print(f"  ... {pct}% ({len(data) / 1024 / 1024:.1f} MB)")

with open(TARGET, "wb") as f:
    f.write(data)

print(f"OK: {TARGET} ({TARGET.stat().st_size / 1024 / 1024:.1f} MB)")
