"""
setup_telegram.py - Telegram bot kurulum sihirbazi.

Adimlar:
    1. BotFather'dan token al (asagida yonergesi).
    2. Token'i bu script'e yapistir.
    3. Telefonundan bota /start yaz (bir kere).
    4. Script chat_id'yi otomatik bulur, .env'e yazar, test mesaji yollar.

Bagimliliklar: yok (sadece stdlib).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"
API = "https://api.telegram.org/bot{token}/{method}"


def api_call(token: str, method: str, **params) -> dict:
    url = API.format(token=token, method=method)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "quantai/0.1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def update_env(token: str, chat_id: str) -> None:
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.is_file() else ""
    lines = text.splitlines()
    updates = {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id}
    seen = set()
    out = []
    for line in lines:
        for k in updates:
            if line.strip().startswith(f"{k}="):
                line = f"{k}={updates[k]}"
                seen.add(k)
                break
        out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def banner() -> None:
    print("=" * 60)
    print("  QuantAI - Telegram Bot Kurulum Sihirbazi")
    print("=" * 60)
    print()
    print("1) Telegram'da @BotFather'i ac")
    print("   https://t.me/BotFather")
    print()
    print("2) Sirayla yaz (BotFather sana cevap verecek):")
    print("     /newbot")
    print("     QuantAI Alpha       <- Bot adi (istedigin)")
    print("     quantai_alpha_bot   <- bot kullanici adi (bos olan)")
    print()
    print("3) BotFather sana TOKEN verecek, soyle gorunur:")
    print("     6789012345:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    print()
    print("4) Bu token'i yapistir.")
    print("-" * 60)


def main() -> int:
    banner()

    token = input("\nBOT TOKEN: ").strip()
    if not token or ":" not in token:
        print("ERR: gecersiz token formati (xxxxx:yyyyy olmali)")
        return 1

    # Token dogrula
    print("\nToken dogrulaniyor...")
    try:
        info = api_call(token, "getMe")
    except Exception as exc:
        print(f"ERR: API cevap vermedi: {exc}")
        return 1
    if not info.get("ok"):
        print(f"ERR: token gecersiz: {info}")
        return 1
    bot = info["result"]
    print(f"OK  bot adi: @{bot['username']}  ({bot.get('first_name')})")

    # chat_id icin /start beklemece
    print()
    print("=" * 60)
    print("5) SIMDI Telegram'da bota git:")
    print(f"   https://t.me/{bot['username']}")
    print()
    print("6) Bota '/start' veya herhangi bir mesaj yaz.")
    print("=" * 60)
    print()
    input("Yaptiktan sonra ENTER'a bas...")

    print("Mesaj araniyor (30 sn)...")
    chat_id = None
    for i in range(15):
        try:
            upd = api_call(token, "getUpdates", timeout=2)
        except Exception as exc:
            print(f"  ... {exc}")
            time.sleep(2)
            continue
        if upd.get("ok") and upd.get("result"):
            for item in reversed(upd["result"]):
                msg = item.get("message") or item.get("edited_message") or {}
                ch = msg.get("chat") or {}
                if ch.get("id"):
                    chat_id = ch["id"]
                    name = ch.get("first_name") or ch.get("username") or "?"
                    print(f"OK  mesaj bulundu, chat_id={chat_id} (kullanici: {name})")
                    break
        if chat_id:
            break
        time.sleep(2)

    if not chat_id:
        print("ERR: mesaj alinamadi. Bota gercekten yazdin mi?")
        print("     Manuel olarak chat_id gir veya tekrar dene.")
        manual = input("Chat ID (atla icin bos): ").strip()
        if not manual:
            return 1
        chat_id = manual

    # Test mesaji
    print("\nTest mesaji gonderiliyor...")
    try:
        send = api_call(
            token, "sendMessage",
            chat_id=str(chat_id),
            text="QuantAI Alpha Engine baglantisi kuruldu.\n"
                 "Bundan sonra ALPHA EVENT bildirimleri buraya gelecek.",
        )
        if not send.get("ok"):
            print(f"WARN: gonderim hatasi: {send}")
    except Exception as exc:
        print(f"WARN: gonderilemedi: {exc}")

    # .env'e yaz
    update_env(token, str(chat_id))
    print(f"\nOK  .env guncellendi: {ENV_FILE}")
    print(f"    TELEGRAM_BOT_TOKEN={token[:12]}...")
    print(f"    TELEGRAM_CHAT_ID={chat_id}")
    print()
    print("Test:")
    print("  python main.py --health   (telegram: true gorunmeli)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nIptal.")
        sys.exit(130)
