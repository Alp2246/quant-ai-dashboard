"""Git for Windows + GitHub CLI indir."""
import json
import urllib.request
import sys
from pathlib import Path

TOOLS = Path("tools")
TOOLS.mkdir(exist_ok=True)


def download(url: str, target: Path, label: str) -> bool:
    if target.exists() and target.stat().st_size > 1_000_000:
        print(f"  OK zaten var: {target} ({target.stat().st_size/1024/1024:.1f} MB)")
        return True
    print(f"  Indir: {label}")
    print(f"    URL: {url}")
    print(f"    Hedef: {target}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            total = int(r.headers.get("Content-Length", "0"))
            print(f"    Boyut: {total/1024/1024:.1f} MB")
            data = bytearray()
            last_pct = -1
            while True:
                b = r.read(65536)
                if not b:
                    break
                data.extend(b)
                if total:
                    pct = len(data) * 100 // total
                    if pct >= last_pct + 20:
                        print(f"      ... {pct}%")
                        last_pct = pct
        target.write_bytes(bytes(data))
        print(f"  OK: {target.stat().st_size/1024/1024:.1f} MB")
        return True
    except Exception as e:
        print(f"  HATA: {e}")
        return False


def latest_git_url() -> str:
    """GitHub API'den en son Git for Windows surumunu bul."""
    api = "https://api.github.com/repos/git-for-windows/git/releases/latest"
    req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    for asset in data["assets"]:
        if asset["name"].endswith("-64-bit.exe") and "Git-" in asset["name"]:
            return asset["browser_download_url"]
    raise RuntimeError("Git installer bulunamadi")


def latest_gh_url() -> str:
    api = "https://api.github.com/repos/cli/cli/releases/latest"
    req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    for asset in data["assets"]:
        if asset["name"].endswith("_windows_amd64.msi"):
            return asset["browser_download_url"]
    raise RuntimeError("gh MSI bulunamadi")


def main() -> int:
    print("[1/2] Git for Windows...")
    git_url = latest_git_url()
    download(git_url, TOOLS / "git-installer.exe", "Git for Windows")
    print()
    print("[2/2] GitHub CLI...")
    gh_url = latest_gh_url()
    download(gh_url, TOOLS / "gh-installer.msi", "GitHub CLI")
    print()
    print("Indirme tamam.")
    print(f"Git installer : {TOOLS / 'git-installer.exe'}")
    print(f"gh installer  : {TOOLS / 'gh-installer.msi'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
