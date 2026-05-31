"""
APK uretici - PWABuilder Cloud API uzerinden.

Akis:
  1. Cloudflare tunnel zaten ayakta (https://*.trycloudflare.com -> :8502)
  2. PWABuilder Android packaging API'sine POST gonder
  3. Donen ZIP dosyasini Downloads/ klasorune indir
  4. ZIP icinden APK'yi cikarip kullaniciya yolu yazdir
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path
from datetime import datetime

TUNNEL_URL = os.environ.get("QUANT_PERMANENT_URL", "https://abozer.tail4ea368.ts.net").rstrip("/")

API_CANDIDATES = [
    "https://pwabuilder-cloudapk.azurewebsites.net/generateAppPackage",
]

DOWNLOADS = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads" / "QuantAI_PERMANENT"
DOWNLOADS.mkdir(parents=True, exist_ok=True)


def build_options() -> dict:
    """PWABuilder CloudAPK Android packaging body (cloudapk.azurewebsites.net format)."""
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
        "iconUrl": f"{TUNNEL_URL}/icons/icon-512.png",
        "includeSourceCode": False,
        "isChromeOSOnly": False,
        "launcherName": "QuantAI",
        "maskableIconUrl": f"{TUNNEL_URL}/icons/icon-maskable-512.png",
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
        "webManifestUrl": f"{TUNNEL_URL}/manifest.webmanifest",
    }


def try_api(endpoint: str, body: dict) -> tuple[bool, str, bytes | None]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/zip,application/octet-stream,*/*",
            "Origin": "https://www.pwabuilder.com",
            "Referer": "https://www.pwabuilder.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        },
        method="POST",
    )
    try:
        print(f"  POST {endpoint}")
        print(f"       (body {len(data)} bytes)")
        with urllib.request.urlopen(req, timeout=180) as r:
            ct = r.headers.get("Content-Type", "")
            content = r.read()
            print(f"       -> HTTP {r.status}  Content-Type: {ct}  Size: {len(content)} bytes")
            return True, ct, content
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")[:500]
        print(f"       -> HTTP {e.code}  {e.reason}")
        print(f"       Body: {body_text}")
        return False, str(e), None
    except Exception as e:
        print(f"       -> ERROR: {e}")
        return False, str(e), None


def main() -> int:
    print(f"PWABuilder Cloud API ile APK uretiliyor...")
    print(f"Tunnel URL: {TUNNEL_URL}")
    print()

    body = build_options()
    print(f"App: {body['name']} ({body['packageId']})")
    print(f"Host: {body['host']}")
    print(f"Manifest: {body['webManifestUrl']}")
    print()

    DOWNLOADS.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for endpoint in API_CANDIDATES:
        ok, ct, content = try_api(endpoint, body)
        if ok and content and len(content) > 1000:
            zip_path = DOWNLOADS / f"QuantAI_APK_{timestamp}.zip"
            with open(zip_path, "wb") as f:
                f.write(content)
            print(f"\nZIP indirildi: {zip_path}")
            print(f"  ({len(content) / 1024:.1f} KB)")

            extract_dir = DOWNLOADS / f"QuantAI_APK_{timestamp}"
            extract_dir.mkdir(exist_ok=True)
            try:
                with zipfile.ZipFile(zip_path) as z:
                    print(f"\nZIP icerigi:")
                    apks = []
                    for name in z.namelist():
                        info = z.getinfo(name)
                        print(f"  {info.file_size:>10} bytes  {name}")
                        if name.endswith(".apk"):
                            apks.append(name)
                    z.extractall(extract_dir)
                if apks:
                    print(f"\n*** APK BULUNDU ***")
                    for apk in apks:
                        full = extract_dir / apk
                        print(f"  -> {full}")
                else:
                    print("\nUYARI: ZIP icinde .apk yok, sadece kaynak/script var")
            except zipfile.BadZipFile:
                print(f"\nUYARI: Dosya ZIP degil (Content-Type: {ct})")
                print(f"  Ilk 500 byte: {content[:500]}")
            return 0
        print()

    print("\nTUM ENDPOINT'LER BASARISIZ")
    print("Cozum: Tarayicida https://www.pwabuilder.com ac, manuel calistir.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
