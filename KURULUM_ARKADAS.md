# Quant AI Dashboard — Tek `.exe` + Telefon Bildirimleri

Selam! Bu dashboard hisse senedi analizi yapar (NVTS, IONQ, ATOM, LAES, QBTS vb.).
Hiçbir kurulum gerekmez — sadece bir `.exe` çalıştırırsın.

**Yeni özellikler:**
- 📲 **Telegram'a anlık bildirim** — kritik haberler telefonuna düşer
- 🚨 **Kırmızı sticky banner** — dashboard üstünde gözden kaçmaz
- 📱 **Telefon uygulaması (PWA)** — Ana ekrana ekle, uygulama gibi açılır
- 📦 **APK** — İstersen Android paketi (rehber: `APK_OLUSTURMA.md`)

---

## 1. Dosya

Tek dosya:

```
QuantDashboard.exe   (yaklaşık 300 MB)
```

İçinde Python, Streamlit, ML kütüphaneleri, 41 modül — hepsi gömülü.

---

## 2. İlk Çalıştırma

1. **Çift tıkla** `QuantDashboard.exe`.
2. Windows "bilinmeyen yayıncı" uyarısı verirse:
   - **"Daha fazla bilgi"** → **"Yine de çalıştır"**
3. Windows Firewall sorarsa: **"Allow access"** (ağ erişimi için)
4. Siyah konsol açılır, banner gözükür:
   ```
   Bilgisayardan      :  http://localhost:8501
   Telefon APP (PWA)  :  http://192.168.X.X:8502
   Telefon (direkt)   :  http://192.168.X.X:8501
   ```
5. 5-10 saniye içinde tarayıcı otomatik açılır.

> Konsolu KAPATMA. Onu kapatırsan uygulama durur.

---

## 3. Telefon Uygulaması (PWA — uygulama gibi)

### Hızlı yol — QR kodu (önerilen)
1. Dashboard açıkken **sol panel** → **"📱 Telefon Uygulaması (PWA + APK)"** aç.
2. **Port 8502** için QR kodu okut (Telefon APP).
3. Android Chrome: menü → **Ana ekrana ekle** / **Uygulamayı yükle**.
4. iPhone Safari: Paylaş → **Ana Ekrana Ekle**.
5. Ana ekranda **QuantAI** ikonu — tıkla, tam ekran dashboard.

### Manuel adres
- **Telefon APP (PWA):** `http://192.168.X.X:8502` ← bunu kullan
- **Direkt dashboard:** `http://192.168.X.X:8501`

> Aynı WiFi şart. Mobil veri için Tailscale/ngrok — `APK_OLUSTURMA.md`.

### Gerçek APK (Android dosyası)
Detaylı adımlar: **`APK_OLUSTURMA.md`** (PWABuilder ile 10 dakikada APK).

---

## 4. Telegram Bildirimleri Kur (Kritik haberler telefona)

Bu en güzel kısım: kritik olaylar (Master Score ≥ 85, NVTS Tier-1 OEM,
LAES NIST PQC, ATOM JDA, AXTI Ga/Ge ihracat...) **telefona Telegram push**
olarak düşer. Bilgisayara bakmasan da bilirsin.

### Adım 1 — Bot oluştur (30 saniye, telefondan)

1. Telegram'ı aç.
2. Arama: **`@BotFather`**.
3. Bota mesaj at: **`/newbot`**.
4. İsim ver: örn. `Quant Alert`.
5. Username ver: örn. `my_quant_alert_bot` (sonu `_bot` olmalı).
6. BotFather sana **token** verir. Şuna benzer:
   ```
   7891234567:AAEhBO-3IsBn1234abcdefghijklmnop
   ```
   Bunu **kopyala**.

### Adım 2 — Botunla konuş (5 sn)

1. Telegram'da yeni botunun ismini ara, sohbeti aç.
2. **`/start`** yaz, gönder.
3. (Bu, chat_id'ni elde etmek için gerekli — dashboard otomatik bulacak)

### Adım 3 — Dashboard'a bağla

1. Dashboard'da **sol panel** → **"📲 Telegram Bildirimleri"** aç.
2. **Bot Token**: BotFather'dan aldığın token'i yapıştır.
3. **"🔍 Chat ID Otomatik Bul"** butonuna bas.
   - Dashboard botundan son mesajını bulup chat_id'ni doldurur.
4. **"🧪 Test Mesajı Gönder"** bas.
   - Telegram'a bir test mesajı gelir → tamamsa hazırsın.
5. **"Bildirimleri AKTİVE et"** kutusunu işaretle.
6. Önem seviyesi: **`KRITIK`** önerilir (sadece çok önemli haberler gelsin).
7. **"💾 Telegram Ayarını Kaydet"** bas.

✅ **Bitti.** Bundan sonra kritik bir olay olduğunda anında Telegram'a push düşer.

---

## 5. Dashboard Sekmeleri

| Sekme | İçerik |
|---|---|
| 💸 **Sanal Portföy** | $1000/hisse simülasyon, anlık PnL, S&P benchmark |
| 📊 **Genel Bakış** | **🚨 KIRMIZI BANNER** (son 24h kritik), tüm hisselerin Master Score'u |
| 🎯 **Detay** | Teknik + sentiment + ML + Monte Carlo 10K + Calculation Trace |
| 🔮 **Forecast** | 6 ay + 10 yıl projeksiyonu (Prophet logistic + reality check) |
| 🏭 **Sektörel** | AI zincirleri, kuantum sepeti, GaN power, PQC |
| 🚀 **Moonshots** | J-Curve büyüme, Explosive Factor (NVTS, RGTI, QBTS, POET vs) |
| 📋 **Yatırımcı Özeti** | Stratejik durum tablosu, Verdict |

---

## 6. Kritik Olaylar Listesi

Bu olaylar telefona Telegram push gönderir:

| Olay | Ne anlama gelir |
|---|---|
| `Master Score ≥ 85` | KRİTİK ALIM sinyali — bütün faktörler yeşil |
| `NVTS Tier-1 OEM` | Navitas birinci sınıf OEM anlaşması imzaladı |
| `NVTS DC Power` | NVIDIA Blackwell / 48V rack power haberi |
| `LAES NIST PQC` | SEALSQ NIST post-quantum cryptography entegrasyonu |
| `LAES PQC Demand` | Q-Day demand spike haberi |
| `ATOM Foundry JDA` | Atomera TSMC/Samsung gibi foundry ile JDA |
| `AXTI Ga/Ge Export` | Çin Galyum/Germanyum ihracat kontrol değişikliği |
| `ML Overfit Severe` | ML modeli aşırı öğrenmiş — tahminlere güvenme |

> Aynı olay 7 gün boyunca tekrar bildirim göndermez (idempotent).

---

## 7. Veri & Cache

```
C:\Users\<senin_adın>\.quant_dashboard\
   ├── launcher.log       (hata logu)
   ├── telegram.json      (bot token + chat_id, sadece sende)
   └── cache\             (Streamlit cache)
```

Silersen sonraki açılışta yeniden indirir, Telegram ayarı silinirse tekrar kurmak gerek.

---

## 8. Sorun Giderme

| Sorun | Çözüm |
|---|---|
| Tarayıcı açılmadı | Manuel git: `http://localhost:8501` |
| Telefon bağlanamıyor | Aynı WiFi mi? Windows Firewall izin verdi mi? |
| Antivirüs blokladı | İstisna ekle (PyInstaller false positive yapar) |
| Telegram test başarısız | Token doğru mu? `/start` gönderdin mi? |
| Chat ID bulunamadı | Botuna önce `/start` gönder, sonra "Otomatik Bul" |
| Veri "N/A" | Borsa kapalıysa veya yfinance gecikme yapıyorsa |

---

## 9. Kapatma

- Konsol penceresinde **Ctrl+C** veya pencereyi kapat.
- Tarayıcı sekmesini kapatmak yetmez — konsol da kapanmalı.

---

## 10. Uyarı

> Bu yazılım **eğitim/araştırma** amaçlıdır. **Yatırım tavsiyesi değildir.**
> Master Score, Monte Carlo simülasyonları geçmiş veriye dayanır.
> Kendi due diligence'ını yap.

---

İyi analizler! 🚀📲
