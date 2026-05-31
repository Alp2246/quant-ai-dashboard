"""
launcher.py - QuantDashboard.exe entry point.

PyInstaller --onefile ile derlendiginde:
  1. Streamlit'i programatik baslatir.
  2. 3 sn sonra default tarayicida http://localhost:8501 acar.
  3. Kullanici Ctrl+C ile veya konsolu kapatarak durdurabilir.

Bundle icinden cikarilan app.py + tum proje .py dosyalari sys._MEIPASS'tan
kullanilir; cache klasoru kullanicinin local appdata'sina yazilir.
"""
import os
import sys
import time
import threading
import webbrowser
import logging

# Hata mesajlarini stderr yerine bir log dosyasina da yaz
LOG_DIR = os.path.join(os.path.expanduser("~"), ".quant_dashboard")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "launcher.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

PORT = 8501
PWA_PORT = 8502


def _bundle_dir() -> str:
    """PyInstaller bundle path'i veya gelistirme dizini."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _open_browser_when_ready():
    """3 sn bekle, sonra tarayici ac."""
    time.sleep(3)
    url = f"http://localhost:{PORT}"
    try:
        webbrowser.open(url)
        logging.info("Browser acildi: %s", url)
    except Exception as e:
        logging.warning("Browser acilamadi: %s", e)


def _local_ip() -> str:
    """LAN IP'sini bul (telefondan erisim icin)."""
    import socket
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


def _print_banner():
    ip = _local_ip()
    banner = r"""
+--------------------------------------------------------------------+
|                                                                    |
|              QUANT AI DASHBOARD v9 - Master Score                  |
|              Yari iletken + Kuantum + Stratejik AI                 |
|                                                                    |
+--------------------------------------------------------------------+

    Streamlit baslatiliyor... Bu pencereyi KAPATMA.

    Bilgisayardan      :  http://localhost:""" + str(PORT) + r"""
    Telefon (kalici)   :  https://abozer.tail4ea368.ts.net
    Telefon (LAN)      :  http://""" + ip + ":" + str(PORT) + r"""

    Durdurmak icin: Ctrl+C (veya pencereyi kapat)
    Log dosyasi:    """ + LOG_FILE + r"""

"""
    print(banner)


def main() -> int:
    _print_banner()

    bundle = _bundle_dir()
    app_path = os.path.join(bundle, "app.py")
    if not os.path.exists(app_path):
        msg = f"HATA: app.py bulunamadi (bundle={bundle})"
        print(msg)
        logging.error(msg)
        input("ENTER ile cik...")
        return 1

    # Cache klasoru kullanicinin appdata'sina; bundle dizinine yazma
    cache_dir = os.path.join(LOG_DIR, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    os.environ.setdefault("STREAMLIT_CONFIG_DIR", cache_dir)
    os.environ.setdefault("XDG_CACHE_HOME", cache_dir)

    # PWA shell (telefon uygulamasi) — port 8502
    try:
        from phone_app_server import serve as serve_pwa
        serve_pwa(PWA_PORT, daemon=True)
        logging.info("PWA server baslatildi port=%d", PWA_PORT)
    except Exception as e:
        logging.warning("PWA server baslatilamadi: %s", e)
        print(f"\n  UYARI: Telefon APP sunucusu baslamadi ({e}).")
        print(f"  Sadece Streamlit (port {PORT}) kullanilabilir.\n")

    # Tarayiciyi arka planda ac
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    # Streamlit'i programatik calistir
    # 0.0.0.0 = telefondan ayni WiFi'de erisim icin (LAN)
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.port", str(PORT),
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--server.runOnSave", "false",
        "--server.fileWatcherType", "none",
        "--browser.gatherUsageStats", "false",
        "--global.developmentMode", "false",
    ]

    try:
        from streamlit.web import cli as stcli
        return stcli.main()
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as e:
        logging.exception("Streamlit catastrophic error")
        print(f"\nHATA: {e}")
        print(f"Detaylar: {LOG_FILE}")
        input("ENTER ile cik...")
        return 1


if __name__ == "__main__":
    sys.exit(main())
