"""Kalici Tailscale Funnel URL ile imzali APK uret."""
from __future__ import annotations
import json
import os
import sys
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

TUNNEL_URL = os.environ.get("QUANT_PERMANENT_URL", "").strip().rstrip("/")
if not TUNNEL_URL:
    # tailscale status --json'dan oku
    import subprocess
    ts = r"C:\Program Files\Tailscale\tailscale.exe"
    if Path(ts).exists():
        out = subprocess.check_output([ts, "status", "--json"], text=True)
        data = json.loads(out)
        dns = data.get("Self", {}).get("DNSName", "").rstrip(".")
        if dns:
            TUNNEL_URL = f"https://{dns}"

if not TUNNEL_URL:
    print("HATA: QUANT_PERMANENT_URL veya Tailscale DNSName gerekli")
    sys.exit(1)

API = "https://pwabuilder-cloudapk.azurewebsites.net/generateAppPackage"
DOWNLOADS = Path(os.environ["USERPROFILE"]) / "Downloads" / "QuantAI_PERMANENT"
DOWNLOADS.mkdir(parents=True, exist_ok=True)


def build_options() -> dict:
    return {
        "additionalTrustedOrigins": [],
        "appVersion": "1.0.0.0",
        "appVersionCode": 1,
        "backgroundColor": "#0e1117",
        "display": "standalone",
        "enableNotifications": True,
        "enableSiteSettingsShortcut": True,
        "fallbackType": "customtabs",
        "features": {
            "locationDelegation": {"enabled": False},
            "playBilling": {"enabled": False},
        },
        "host": TUNNEL_URL,
        "iconUrl": f"{TUNNEL_URL}/app/static/icons/icon-512.png",
        "includeSourceCode": False,
        "isChromeOSOnly": False,
        "launcherName": "QuantAI",
        "maskableIconUrl": f"{TUNNEL_URL}/app/static/icons/icon-maskable-512.png",
        "monochromeIconUrl": None,
        "name": "Quant AI Dashboard",
        "navigationColor": "#0e1117",
        "navigationColorDark": "#0e1117",
        "navigationDividerColor": "#0e1117",
        "navigationDividerColorDark": "#0e1117",
        "orientation": "default",
        "packageId": "com.quantai.dashboard",
        "serviceAccountJsonFile": None,
        "shareTarget": None,
        "shortcuts": [],
        "signing": {
            "file": None,
            "alias": "quantai",
            "fullName": "Quant AI Dashboard",
            "organization": "Quant AI",
            "organizationalUnit": "Engineering",
            "countryCode": "TR",
            "keyPassword": "quantai2026",
            "storePassword": "quantai2026",
        },
        "signingMode": "new",
        "splashScreenFadeOutDuration": 300,
        "startUrl": "/",
        "themeColor": "#0e1117",
        "themeColorDark": "#0e1117",
        "webManifestUrl": f"{TUNNEL_URL}/app/static/manifest.webmanifest",
    }


def main() -> int:
    print(f"Kalici APK uretiliyor...")
    print(f"URL: {TUNNEL_URL}")
    body = build_options()
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/zip,*/*",
            "Origin": "https://www.pwabuilder.com",
            "Referer": "https://www.pwabuilder.com/",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            content = r.read()
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:800]
        print(f"API HTTP {e.code}: {err}")
        return 1
    print(f"ZIP: {len(content) / 1024:.0f} KB")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = DOWNLOADS / f"QuantAI_PERMANENT_{ts}.zip"
    zip_path.write_bytes(content)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(DOWNLOADS)
        apks = [n for n in z.namelist() if n.endswith(".apk") and "unsigned" not in n.lower()]
    for name in apks:
        src = DOWNLOADS / name
        dst = DOWNLOADS / "QuantAI-Dashboard.apk"
        dst.write_bytes(src.read_bytes())
        print(f"APK: {dst}")
    (DOWNLOADS / "PERMANENT_URL.txt").write_text(
        f"Kalici HTTPS URL:\n{TUNNEL_URL}\n\n"
        f"Bu URL Tailscale Funnel ile bagli.\n"
        f"PC acik + QuantDashboard.exe + Funnel aktif olmali.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
