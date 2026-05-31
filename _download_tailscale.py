"""Tailscale Windows MSI indir (~40 MB)."""
import urllib.request
import sys
from pathlib import Path

TARGET = Path("tools/tailscale-setup.msi")
URL = "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi"

TARGET.parent.mkdir(parents=True, exist_ok=True)

if TARGET.exists() and TARGET.stat().st_size > 10_000_000:
    print(f"OK zaten var: {TARGET} ({TARGET.stat().st_size / 1024 / 1024:.1f} MB)")
    sys.exit(0)

print(f"Indiriliyor: {URL}")
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=180) as r:
    total = int(r.headers.get("Content-Length", "0"))
    print(f"Boyut: {total / 1024 / 1024:.1f} MB")
    data = bytearray()
    last_pct = -1
    while True:
        b = r.read(65536)
        if not b:
            break
        data.extend(b)
        if total:
            pct = len(data) * 100 // total
            if pct >= last_pct + 10:
                print(f"  ... {pct}% ({len(data) / 1024 / 1024:.1f} MB)")
                last_pct = pct

with open(TARGET, "wb") as f:
    f.write(data)
print(f"OK: {TARGET} ({TARGET.stat().st_size / 1024 / 1024:.1f} MB)")
