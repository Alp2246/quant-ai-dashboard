# Oracle Cloud'a Kurulum — 7/24 Çalışan Sunucu (TAMAMEN ÜCRETSİZ)

Bu rehberi takip ettiğinde:
- PC'n kapalı olsa bile telefondan **`https://abozer.tail4ea368.ts.net`** açılır
- Telegram'a uyarılar otomatik gelir (engine sunucuda çalışır)
- APK'yı değiştirmeye **gerek yok** (aynı Tailscale URL kullanılır)
- **Aylık 0 TL** ödersin (Oracle Always Free Tier — kart bilgisi alınır ama çekilmez)

---

## TOPLAM SÜRE: ~30 dakika (ilk seferinde)

| Adım | Süre | Ne yapacaksın |
|---|---|---|
| 1 | 10 dk | Oracle Cloud hesap aç |
| 2 | 5 dk | ARM Ubuntu VM oluştur |
| 3 | 5 dk | SSH ile bağlan |
| 4 | 10 dk | Tek komutla kur (kurulum scripti çalışır) |

---

## ADIM 1: Oracle Cloud hesabı

1. https://www.oracle.com/cloud/free/ adresine git
2. **"Start for free"** tıkla
3. E-posta, ülke (Türkiye), telefon ver
4. **Kredi kartı bilgisi** istenir → tedirgin olma, sadece kimlik doğrulama. **Always Free** kaynakları için ücret ÇEKİLMEZ.
   - Önemli: Hesabı "Pay As You Go"ya yükseltmediğin sürece hiçbir şey ödemezsin
5. Doğrulama maili gelir, onayla
6. **Home Region** seç: `Germany Central (Frankfurt)` veya `UK South (London)` → Türkiye'den en hızlı

> Sorun yaşarsan: Hesap doğrulama bazen 24 saat alabilir. Sabırlı ol.

---

## ADIM 2: ARM Ubuntu VM oluştur

1. Console'a giriş yap: https://cloud.oracle.com
2. Sol üst hamburger menü → **Compute → Instances**
3. **Create Instance** butonu
4. Aşağıdaki ayarları yap:

| Alan | Değer |
|---|---|
| **Name** | `quantai-server` |
| **Image** | "Change image" → **Ubuntu 22.04** (Minimal değil normal) |
| **Shape** | "Change shape" → **Ampere → VM.Standard.A1.Flex** |
| **OCPU** | **2** (Always Free limit: 4 toplam) |
| **Memory (GB)** | **12** (Always Free limit: 24 toplam) |
| **VNIC** | Default (Auto-create public IP) |
| **SSH Keys** | "Generate a key pair" → **Save private key** (`.key` dosyası) |
| **Boot Volume** | Default (47 GB Always Free) |

5. **Create** bas → ~2 dakika sonra "Running" olur
6. **Public IP Address**'i not al (örn: `132.226.45.123`)

> **Önemli:** İndirdiğin `.key` dosyasını kaybetme. Bu olmadan sunucuya giremezsin. `C:\Users\oalpe\.ssh\quantai.key` gibi bir yere koy.

---

## ADIM 3: Firewall portunu aç

Oracle default sadece SSH (22) portunu açıyor. Streamlit için 8501 lazım — ama Tailscale Funnel kullanacağımız için sadece SSH yeterli aslında. **Bu adımı atlayabilirsin.**

(Eğer doğrudan public IP üzerinden de erişmek istersen Networking → VCN → Security List → Ingress Rule ekle: TCP 8501 source `0.0.0.0/0`)

---

## ADIM 4: SSH ile bağlan

PowerShell'de:

```powershell
# Önce key permission'ı düzelt (Windows)
icacls "C:\Users\oalpe\.ssh\quantai.key" /inheritance:r
icacls "C:\Users\oalpe\.ssh\quantai.key" /grant:r "$($env:USERNAME):(R)"

# Bağlan
ssh -i C:\Users\oalpe\.ssh\quantai.key ubuntu@132.226.45.123
```

`yes` yaz ilk soruda. Bağlandığında `ubuntu@quantai-server:~$` görmen lazım.

---

## ADIM 5: Tek komutla kurulum

Sunucuya bağlıyken **şu komutu çalıştır** — her şeyi otomatik kurar:

```bash
curl -fsSL https://raw.githubusercontent.com/abozer/quant-dashboard/main/deploy/bootstrap.sh | bash
```

> **Henüz GitHub'a push yapmadıysan** (yapmadın çünkü o adım pending), alternatif yöntemi kullan: dosyaları kendi PC'nden sunucuya kopyala.

### Alternatif: PC'den dosya transferi

PowerShell'de (Tek seferlik tüm projeyi yolla):

```powershell
cd C:\fpga_work
# rsync yoksa scp ile (Windows 10+):
scp -i C:\Users\oalpe\.ssh\quantai.key -r quant-dashboard ubuntu@132.226.45.123:~/
```

Sonra sunucuda:

```bash
cd ~/quant-dashboard
bash deploy/bootstrap.sh
```

---

## ADIM 6: Tailscale bağla (önemli!)

Kurulum sırasında script seni Tailscale login linkine yönlendirecek:

```
To authenticate, visit:
    https://login.tailscale.com/a/abc123def456
```

Bu linki **kendi PC'nde** aç → Tailscale hesabınla giriş yap (zaten kurulu) → **"Connect"** bas.

Sonra script otomatik devam eder:
1. ✅ Tailscale node olarak ekler
2. ✅ Node ismini `abozer` yapar (eski PC'nin yerine geçer)
3. ✅ Tailscale Funnel açar
4. ✅ Streamlit + Alpha Engine systemd servisleri başlatır
5. ✅ Sunucu açıldıkça her şey otomatik açılır

---

## ADIM 7: Test et

Telefondan APK'yı aç → **çalışıyor olmalı** çünkü:
- Aynı URL: `https://abozer.tail4ea368.ts.net`
- Aynı Tailscale node ismi
- Yeni sunucu eski PC'nin yerine geçer

Telegram'a da **birkaç dakika içinde** sunucu başlangıç pingi gelir:

```
✅ QuantAI Erken Uyari Motoru AKTIF
```

---

## ADIM 8: PC'yi kapat

Artık PC'n tamamen kapalı olabilir. Sunucuda:
- Streamlit her zaman çalışır (`systemctl status streamlit`)
- Alpha Engine dakika başı tarama yapar (`systemctl status alpha-engine`)
- Sistem yeniden başlasa bile (sunucu reboot) otomatik açılır
- Crash olursa otomatik restart eder

---

## SERVİS YÖNETİMİ

Sunucuda işine yarayacak komutlar:

```bash
# Durum kontrol
sudo systemctl status streamlit alpha-engine

# Logları takip et
sudo journalctl -fu streamlit
sudo journalctl -fu alpha-engine

# Restart
sudo systemctl restart streamlit alpha-engine

# Tailscale durumu
tailscale status
tailscale funnel status

# Disk kullanımı
df -h
```

---

## GÜNCELLEMELERİ NASIL DEPLOY EDERSİN?

PC'nde kod değişikliği yaptıktan sonra **tek komutla** sunucuya yolla:

```powershell
cd C:\fpga_work\quant-dashboard
deploy\deploy_to_oracle.bat
```

Bu script:
1. Değişen dosyaları rsync ile sunucuya yollar
2. Sunucuda servisleri restart eder
3. ~5 saniyede tamamlar

---

## SORUN GİDERME

### "Sunucuya bağlanamıyorum"
```powershell
# Public IP doğru mu? Console → Instances → Details
# Firewall: Oracle Console → VCN → Security Lists → Default → Ingress
# SSH port 22 açık mı?
```

### "Streamlit açılmıyor"
```bash
sudo systemctl status streamlit
sudo journalctl -u streamlit -n 50
# Genelde .env eksiktir → ~/.quant-dashboard/.env doldur
```

### "Telegram bot ping atmıyor"
```bash
sudo systemctl status alpha-engine
# .env'de TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID var mı?
sudo journalctl -u alpha-engine -n 100 | grep -i telegram
```

### "Tailscale URL açılmıyor" / ERR_SSL_PROTOCOL_ERROR / ERR_CONNECTION_ABORTED

Sunucu çalışıyorsa sorun çoğu zaman **PC'de Tailscale + MagicDNS** kaynaklıdır:
`https://abozer-1.tail4ea368.ts.net` adresi tarayıcıda **100.89.x.x** (özel IP) olarak çözülür;
Funnel'un genel HTTPS yolu atlanır ve bağlantı kopar.

**Hemen deneyin (PC, Tailscale açık):**

```
http://abozer-1:8080
```

**HTTPS ile aynı adres (PC):**

1. Tailscale simgesi → **Settings** → **DNS** → **Use Tailscale DNS** → **KAPALI**
2. Tarayıcıyı kapatıp açın, tekrar: `https://abozer-1.tail4ea368.ts.net`

**Telefon / APK (Tailscale yok):** `https://abozer-1.tail4ea368.ts.net` genelde doğrudan çalışır.

**Sunucuda kontrol:**
```bash
curl -sI http://127.0.0.1:8080/ | head -3
sudo tailscale funnel status
# Bos veya 502 ise:
sudo tailscale funnel reset
sudo tailscale funnel --bg 8080
sudo systemctl restart nginx
```

Funnel, nginx üzerinden Streamlit'e gider (WebSocket için port **8080**, doğrudan 8501 değil).

---

## MALIYET / LIMIT

Always Free Tier limitleri:
- **4 ARM OCPU + 24 GB RAM** — biz 2 OCPU + 12 GB kullanıyoruz (yarısı)
- **200 GB block storage** — bizim 47 GB
- **10 TB / ay outbound trafik** — çok bol
- **Bandwidth limitsiz**

**Yapma:** Hesabını "Pay As You Go"ya yükseltme — Always Free tier'da kal.

---

Yardım gerekirse: `KURULUM_ARKADAS.md` dosyasını da oku.
