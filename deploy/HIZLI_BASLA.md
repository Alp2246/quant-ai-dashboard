# HIZLI BAŞLA — Oracle Cloud'a Geçiş (30 dk)

## Yapılacaklar (sırayla)

### 1. Oracle hesap (~10 dk)
- https://www.oracle.com/cloud/free/ → "Start for free"
- Türkiye, telefon, e-posta, kart bilgisi (ücret çekilmez)
- Onay e-postası gelince oturum aç
- **Region**: Germany Frankfurt seç

### 2. VM oluştur (~5 dk)
- Console → Compute → Instances → **Create Instance**
- **Image**: Ubuntu 22.04
- **Shape**: Ampere VM.Standard.A1.Flex → **2 OCPU, 12 GB RAM**
- **SSH Keys**: Generate → **private key indir** (`.key` dosyası)
- Create
- **Public IP** not al (örn: `132.226.45.123`)

### 3. Key dosyasını koy
```powershell
# İndirilen .key dosyasını buraya kopyala:
mkdir C:\Users\oalpe\.ssh -Force
move C:\Users\oalpe\Downloads\ssh-key-*.key C:\Users\oalpe\.ssh\quantai.key

# Permission düzelt
icacls C:\Users\oalpe\.ssh\quantai.key /inheritance:r
icacls C:\Users\oalpe\.ssh\quantai.key /grant:r "$($env:USERNAME):(R)"
```

### 4. SSH bağlan + dosyaları yolla (~5 dk)

```powershell
# IP'yi değiştir
$SERVER_IP = "132.226.45.123"

# Test bağlantı
ssh -i C:\Users\oalpe\.ssh\quantai.key ubuntu@$SERVER_IP "echo OK"
# yes deyince OK görürsün

# Tüm projeyi yolla (10-20 saniye)
cd C:\fpga_work
scp -i C:\Users\oalpe\.ssh\quantai.key -r quant-dashboard ubuntu@${SERVER_IP}:~/
```

### 5. Sunucuda kurulum (~10 dk)

```powershell
# Bağlan
ssh -i C:\Users\oalpe\.ssh\quantai.key ubuntu@$SERVER_IP
```

Sunucuda:

```bash
cd ~/quant-dashboard
bash deploy/bootstrap.sh
```

Script Tailscale link gösterecek → **PC tarayıcında aç** → giriş yap → "Connect" → script devam eder.

### 6. .env dosyası

Bootstrap `.env`'i otomatik kopyalamıyor (güvenlik). Manuel yolla:

```powershell
# PC'den (kendi makinen)
scp -i C:\Users\oalpe\.ssh\quantai.key `
    C:\fpga_work\quant-dashboard\alpha_engine\.env `
    ubuntu@${SERVER_IP}:~/quant-dashboard/alpha_engine/.env

# Sunucuda restart
ssh -i C:\Users\oalpe\.ssh\quantai.key ubuntu@$SERVER_IP `
    "sudo systemctl restart streamlit alpha-engine"
```

### 7. Test
- Telefondan APK'yı aç → **çalışıyor olmalı**
- Telegram'a 1-2 dakika içinde "✅ QuantAI Erken Uyari Motoru AKTIF" gelir

### 8. PC'yi kapat
İş bitti. Artık sunucuda 7/24 çalışıyor.

---

## SONRADAN GÜNCELLEME

Kodu değiştirdiğinde:

```powershell
cd C:\fpga_work\quant-dashboard
deploy\deploy_to_oracle.bat
```

IP'yi ilk seferinde sorar, kaydeder. Bir daha sormaz. Tek komutla deploy + restart.

---

## YARDIM
- Detay rehber: `deploy\ORACLE_KURULUM.md`
- Sorun varsa: `sudo journalctl -fu streamlit` veya `sudo journalctl -fu alpha-engine`
