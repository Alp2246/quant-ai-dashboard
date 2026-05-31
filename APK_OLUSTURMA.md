# Quant AI Dashboard - APK Olusturma Rehberi

> **TLDR:** `make_apk.ps1` cift tikla, acilan tarayicida 3 buton bas, APK in.

---

## Neden LAN URL calismadi?

PWABuilder.com **bulutta** calisir. `192.168.x.x` adresine internetten erisemez
ve **HTTPS** ister. LAN URL'n telefondan calisir ama PWABuilder'dan calismaz.

Cozum: Bilgisayarinin port 8502'sini **gecici public HTTPS URL**'ye cevir.

---

## En Kolay Yol: `make_apk.ps1` (Cloudflare Tunnel)

### Adim 1 - Dashboard acik olsun

Once `QuantDashboard.exe` (veya `python launcher.py`) calistir.
Konsol banner'inda **`Telefon APP (PWA): http://IP:8502`** yazmali.

### Adim 2 - APK helper'i calistir

```powershell
cd C:\fpga_work\quant-dashboard
.\make_apk.ps1
```

Script otomatik olarak:

1. **cloudflared.exe**'yi indirir (sadece ilk seferinde, ~20 MB)
2. PWA sunucu kontrolu yapar (port 8502)
3. **HTTPS public URL** olusturur: `https://xxxx-yyyy.trycloudflare.com`
4. URL'yi **panoya kopyalar**
5. Tarayicida **PWABuilder.com**'u acar (URL onceden doldurulmus halde)

### Adim 3 - PWABuilder'da 3 tik

1. **Start** (URL zaten dolu)
2. Manifest/SW yesil isaretleri bekle (~10 sn)
3. **Package For Stores** -> **Android** -> **Generate Package**
4. ZIP iner. Icinden:
   - `app-release-signed.apk` -> Google Play disi yukleme
   - veya unsigned `.apk`

### Adim 4 - Telefona kur

1. APK'yi telefona aktar (Google Drive / e-posta / USB / WhatsApp).
2. Android: **Ayarlar -> Bilinmeyen uygulamalara izin ver**.
3. Dosyaya tikla -> Kur.
4. **QuantAI** ikonu ana ekranda. Tikla, acil.

### Adim 5 - APK uretimi bittikten sonra

PowerShell penceresini kapat. Tunnel durur (zaten gerekmiyor).

---

## ONEMLI: APK kalici nasil olur?

`make_apk.ps1` her seferinde **farkli URL** verir (trycloudflare gecici).
APK icindeki URL **uretildigi anki** URL'ye sabitlenir.

### Sorun
Tunnel kapaninca, telefonda APK acilinca **"Sayfa yuklenemiyor"** der.

### Cozum A: Telefonda VPN/LAN ile sinirla
`make_apk.ps1` calistirmadan once `phone_app/manifest.webmanifest` ve
`phone_app/index.html` icindeki `start_url` / `scope`'u LAN IP'ye cevir.
Boylece APK her zaman LAN'a baglanir.

### Cozum B: Kalici tunnel (onerilen)
[Cloudflare Zero Trust](https://dash.cloudflare.com/) ucretsiz hesap ac:

```powershell
cd C:\fpga_work\quant-dashboard\tools
.\cloudflared.exe tunnel login
.\cloudflared.exe tunnel create quant-dashboard
.\cloudflared.exe tunnel route dns quant-dashboard quant.SENIN-DOMAIN.com
.\cloudflared.exe tunnel run --url http://localhost:8502 quant-dashboard
```

Sonra `make_apk.ps1` yerine `https://quant.SENIN-DOMAIN.com` URL'siyle
PWABuilder'a git. APK kalici olur (URL hep ayni).

### Cozum C: Tailscale (en pratik, kalici)
[tailscale.com](https://tailscale.com/) -> bilgisayara ve telefona kur.
Telefon Tailscale aciksa LAN'daymis gibi `http://100.x.y.z:8502` calisir.
APK olusturmaya gerek kalmaz — PWA yeterlidir.

---

## Alternatif: ngrok (Cloudflare olmazsa)

```powershell
# https://ngrok.com/download -> ngrok.exe indir
.\ngrok.exe http 8502
```

Cikan `https://xxxx.ngrok-free.app` URL'sini PWABuilder'a yapistir.
Free hesap: oturum basi yeni URL (Cloudflare gibi).

---

## Manuel adimlar (script calismazsa)

1. **cloudflared.exe** indir:
   https://github.com/cloudflare/cloudflared/releases/latest
   `cloudflared-windows-amd64.exe` -> tools/ klasorune koy.

2. PowerShell:
   ```powershell
   cd C:\fpga_work\quant-dashboard
   .\tools\cloudflared.exe tunnel --url http://localhost:8502
   ```

3. Ciktida `https://*.trycloudflare.com` URL'sini kopyala.

4. https://www.pwabuilder.com -> URL'yi yapistir -> Android paket.

---

## Sorun Giderme

| Sorun | Cozum |
|-------|--------|
| `make_apk.ps1` "execution policy" hatasi | `Set-ExecutionPolicy -Scope Process Bypass` |
| cloudflared indirilemiyor | Manuel indir (yukaridaki link), tools/ icine koy |
| PWABuilder "manifest not found" | Tunnel acik mi? URL tarayicida test et: `URL/manifest.webmanifest` |
| PWABuilder "service worker missing" | Yine tunnel; `URL/service-worker.js` test et |
| APK kuruluyor ama acmiyor | Telefonda **bilinmeyen kaynaklar** izni yok |
| APK aciliyor ama dashboard yuklenmiyor | Tunnel kapanmis; Cozum B veya C kullan |
| `make_apk.ps1` "URL alinamadi" | Cloudflare baska bolge deniyor; tekrar calistir |

---

## Bonus: Local APK (Bubblewrap - JDK gerekir)

Sadece tecrubeli kullanicilar. Node.js + Java JDK 17 + Android SDK lazim:

```powershell
npm install -g @bubblewrap/cli
cd C:\fpga_work\quant-dashboard
bubblewrap init --manifest https://SENIN-TUNNEL-URL/manifest.webmanifest
bubblewrap build
```

Cikti: `app-release-signed.apk` (kalici imzali).

---

## Ozet

| Senaryo | Onerilen |
|---------|----------|
| Hemen APK istiyorum, gecici URL ok | `.\make_apk.ps1` |
| APK kalici olsun, domain'im var | Cozum B (Cloudflare Tunnel + DNS) |
| APK gerek yok, telefonda kullanayim | Tailscale + PWA (`Ana ekrana ekle`) |
| Tam kontrol istiyorum | Bubblewrap (gelismis) |
