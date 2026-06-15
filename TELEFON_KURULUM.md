# QuantAI Dashboard - Telefon Kurulumu

## TEK APK DOSYASI

**Konum:**
- `C:\Users\oalpe\Desktop\QuantAI.apk` (Masaüstü)
- `C:\Users\oalpe\Downloads\QuantAI-WebView.apk` (İndirilenler)

**Boyut:** 0.42 MB (çok küçük)

---

## Telefona Kurma (3 adım)

### 1) APK'yı telefona aktar
Aşağıdaki yöntemlerden birini seç:

**A) WhatsApp / Telegram (kolay)**
- Kendine `QuantAI.apk` dosyasını gönder
- Telefondan indir

**B) USB kablo**
- Telefonu PC'ye USB ile bağla
- `QuantAI.apk` dosyasını telefonun `Downloads` klasörüne kopyala

**C) Google Drive / OneDrive**
- APK'yı yükle, telefondan indir

### 2) Bilinmeyen kaynaklara izin ver
- Telefonda APK'ya dokun → "Kuruluma izin yok" uyarısı çıkarsa:
- **Ayarlar → Uygulamalar → Özel uygulama erişimi → Bilinmeyen kaynakları yükle**
- Kullandığın tarayıcı/dosya yöneticisini seç → **İzin ver**

### 3) Kur ve aç
- `QuantAI.apk`'ya dokun → **Kur** → **Aç**
- Logo: QuantAI
- İkonu telefon ana ekranında olacak

---

## Çalışması için ŞART olan adımlar (Bilgisayarda)

APK telefondan internete bağlanarak senin PC'ndeki dashboard'a erişiyor. **PC'nin açık olması ŞART**.

Her PC açıldığında bu 3 servis çalışıyor olmalı:
1. **Streamlit** (port 8501)
2. **Gateway** (port 8502)
3. **Tailscale Funnel** (port 8502 → `https://abozer.tail4ea368.ts.net`)

**Tek tıkla başlat:** Masaüstündeki `start_dashboard.bat` dosyasını çift tıkla. Bunu açık bırak — kapatma.

**Otomatik başlatma için:**
```powershell
powershell -ExecutionPolicy Bypass -File install_autostart.ps1
```
Bu, PC her açıldığında dashboard'ı arka planda başlatır.

---

## Sorun: APK açılıyor ama içerik gelmiyor

Demek ki PC'deki dashboard kapalı veya internete açık değil. Kontrol:

1. PC açık mı? `start_dashboard.bat` çalışıyor mu?
2. Funnel açık mı? PC'de tarayıcıdan aç: https://abozer.tail4ea368.ts.net
   - Dashboard görmen lazım. Gelmiyorsa Funnel sorunlu.
3. Funnel'ı resetle:
   ```cmd
   "C:\Program Files\Tailscale\tailscale.exe" funnel reset
   "C:\Program Files\Tailscale\tailscale.exe" funnel --bg 8502
   ```

APK içinde otomatik **"Tekrar Dene"** butonu var; bilgisayarı açtıktan sonra ona basman yeterli.

---

## Teknik Detay (WebView APK)

Bu APK **TWA değil**, plain Android WebView. Avantajları:
- Chrome'un yüklü olmasına gerek yok
- assetlinks.json doğrulama gerek yok
- Fingerprint mismatch sorunu yok
- Android 5.0+ tüm cihazlarda çalışır
- 425 KB — anında kurulur

İçinde sadece bir WebView var; `https://abozer.tail4ea368.ts.net` adresini açar.
Tarayıcıdaki tüm grafikler, etkileşimler, bildirimler aynen çalışır.

---

## Eğer APK hala açılmıyorsa

Telefonun Android sürümünü söyle (Ayarlar → Telefon hakkında → Android sürümü).
APK Android **5.0 (API 21)** ve üzeri için. Aşağıdaki sürümlerde çalışmaz (% 99 telefon uygundur).
