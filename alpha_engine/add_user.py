"""
add_user.py - Telegram'a yeni kullanici ekle.

Kullanim:
    python add_user.py

Calistirildiginda:
    1) Bota dokunan TUM yeni mesajlari getUpdates ile cekiyor
    2) Henuz .env'de kayitli olmayan chat_id'leri gosteriyor
    3) Eklemek istediklerini seciyorsun
    4) .env guncelleniyor + her birine test mesaji gidiyor

ON KOSUL:
    Eklenecek kisi telefonunda @quantai_alpha_bot'u acmis ve /start
    veya herhangi bir mesaj YAZMIS olmali. Bot, kullanici ilk yazmadan
    mesaj gonderemez (Telegram spam korumasi).
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import settings  # noqa: E402

ENV = Path(__file__).parent / ".env"


def _api(method: str, **params) -> dict:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise SystemExit("Hata: .env icinde TELEGRAM_BOT_TOKEN yok.")
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def list_known_chats() -> list[str]:
    return settings.telegram_chat_ids


def list_pending_chats() -> list[dict]:
    """getUpdates'tan benzersiz chat'leri toplar (henuz .env'de olmayanlar)."""
    known = set(list_known_chats())
    upd = _api("getUpdates", limit=100)
    if not upd.get("ok"):
        raise SystemExit(f"getUpdates hata: {upd}")

    seen = {}
    for item in upd.get("result", []):
        msg = item.get("message") or item.get("edited_message") or {}
        ch = msg.get("chat") or {}
        cid = str(ch.get("id") or "")
        if not cid:
            continue
        if cid in known:
            continue
        if cid in seen:
            continue
        seen[cid] = {
            "chat_id": cid,
            "first_name": ch.get("first_name") or "",
            "last_name": ch.get("last_name") or "",
            "username": ch.get("username") or "",
            "type": ch.get("type") or "?",
            "last_text": (msg.get("text") or "")[:80],
        }
    return list(seen.values())


def write_env(new_ids: list[str]) -> None:
    cur = list_known_chats()
    merged = list(dict.fromkeys(cur + new_ids))   # benzersiz, sira korunur
    new_line = "TELEGRAM_CHAT_ID=" + ",".join(merged)

    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.is_file() else []
    out = []
    seen = False
    for line in lines:
        if line.strip().startswith("TELEGRAM_CHAT_ID="):
            out.append(new_line)
            seen = True
        else:
            out.append(line)
    if not seen:
        out.append(new_line)
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")


def send_welcome(chat_id: str) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    text = (
        "Merhaba! 👋\n\n"
        "QuantAI Erken Uyari Motoru'na <b>basariyla eklendin</b>.\n\n"
        "Bundan sonra Wolfspeed, IonQ, AXTI, NVDA gibi hisselerde "
        "<b>onemli olaylar</b> oldugunda (SEC bildirimi, haber spike, "
        "Reddit dalgasi) bu kanala bildirim gelecek.\n\n"
        "Test mesaji - sistem calisiyor. ✅"
    )
    try:
        payload = urllib.parse.urlencode({
            "chat_id": chat_id, "text": text, "parse_mode": "HTML",
        }).encode("utf-8")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as exc:
        print(f"  WARN gonderilemedi: {exc}")
        return False


def main() -> int:
    print("=" * 60)
    print("  QuantAI - Telegram Kullanici Ekleme Sihirbazi")
    print("=" * 60)
    known = list_known_chats()
    print(f"\nMevcut kayitli kullanicilar: {len(known)}")
    for cid in known:
        print(f"  • {cid}")

    print("\nYeni kullanicilar araniyor (getUpdates)...")
    print("(Eklenecek kisi @quantai_alpha_bot'a /start yazmis olmali!)")
    print()

    pending = list_pending_chats()
    if not pending:
        print("Yeni kullanici bulunamadi.")
        print()
        print("Eklenecek kisi sunu yapsin:")
        print("  1) Telegram'da @quantai_alpha_bot 'u acsin")
        print("  2) START butonuna bassin (veya /start yazsin)")
        print("  3) Sen tekrar bu script'i calistir")
        return 1

    print(f"Bulunan {len(pending)} yeni kullanici:\n")
    for i, c in enumerate(pending, 1):
        name = (c["first_name"] + " " + c["last_name"]).strip() or "?"
        un = f"@{c['username']}" if c["username"] else ""
        print(f"  [{i}] {name} {un}")
        print(f"      chat_id: {c['chat_id']}  tip: {c['type']}")
        print(f"      son mesaj: {c['last_text'] or '(bos)'}")
        print()

    print("Eklemek istediklerinin numarasini virgulle ayir (orn: 1,2)")
    print("'a' = tumunu ekle, 'q' = iptal")
    choice = input(">>> ").strip().lower()
    if choice in ("q", ""):
        print("Iptal.")
        return 0

    selected: list[dict] = []
    if choice == "a":
        selected = pending
    else:
        try:
            idxs = [int(x.strip()) - 1 for x in choice.split(",") if x.strip()]
            selected = [pending[i] for i in idxs if 0 <= i < len(pending)]
        except (ValueError, IndexError) as exc:
            print(f"Gecersiz secim: {exc}")
            return 1

    if not selected:
        print("Hicbir kullanici secilmedi.")
        return 0

    new_ids = [c["chat_id"] for c in selected]
    write_env(new_ids)
    print(f"\nOK  .env guncellendi: +{len(new_ids)} kullanici")

    # Hosgeldin mesaji
    print("\nHosgeldin mesajlari gonderiliyor...")
    for c in selected:
        ok = send_welcome(c["chat_id"])
        name = c["first_name"] or c["chat_id"]
        print(f"  {'OK' if ok else 'FAIL'}  {name}")

    print("\nBitti! Yeni tickte herkes uyarilari alacak.")
    print("Eger motor calismiyorsa:  ..\\venv\\Scripts\\python.exe main.py")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nIptal.")
        sys.exit(130)
