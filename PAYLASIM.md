# Arkadaşlara Paylaşım (PC üzerinden)

## Tek tık başlat

Masaüstü veya proje klasöründe çift tık:

```
paylasim_baslat.bat
```

veya

```
start_dashboard.bat
```

**Bu pencereyi kapatma** — kapatırsan link çalışmaz.

---

## Arkadaşlara göndereceğin link

```
https://abozer.tail4ea368.ts.net
```

- Tailscale hesabı **gerekmez**
- Telefon / tablet / başka şehirden açılır
- İlk yükleme 1–3 dakika sürebilir (tüm hisseler hesaplanıyor)

---

## Senin bilgisayarda açmak için

| Adres | Ne zaman |
|--------|----------|
| http://localhost:8501 | En güvenilir (aynı PC) |
| https://abozer.tail4ea368.ts.net | Paylaşım linki ile aynı |

**Kendi PC’nde** `https://abozer...` açılmazsa (SSL hatası): Tailscale → Settings → DNS → **Use Tailscale DNS** kapat, tarayıcıyı yeniden başlat. Arkadaşların etkilenmez.

---

## Çalışması için şartlar

1. PC açık ve `paylasim_baslat.bat` çalışıyor
2. İnternet bağlantısı var
3. Tailscale açık (sistem tepsisinde)
4. [Tailscale Admin](https://login.tailscale.com/admin/acls) → **Funnel** tailnet’te açık

---

## Telegram bildirimleri (isteğe bağlı)

`alpha_engine\.env` içinde:

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

`paylasim_baslat.bat` Alpha Engine’i de başlatır → kritik haberler telefona düşer.

---

## Sık sorunlar

| Sorun | Çözüm |
|--------|--------|
| Arkadaş açamıyor | PC kapalı mı? Funnel çalışıyor mu? `tailscale funnel status` |
| Çok yavaş | Normal — ilk açılış ağır; 15 dk cache var |
| Siyah ekran | Funnel 8501’e bağlı olmalı (8502 gateway kullanma) |

---

## Oracle sunucu linki (alternatif)

PC kapalıyken:

```
http://abozer-1:8080
```

(sadece senin Tailscale ağın — arkadaşlar için PC + Funnel veya sunucuda Funnel gerekir)
