# =============================================================================
#  make_apk.ps1  --  Tek-tikla APK olusturma yardimcisi
# =============================================================================
#  Ne yapar?
#    1) cloudflared.exe yoksa indirir (~20 MB, internet'e cikar)
#    2) PWA server'in (port 8502) ayakta olup olmadigini kontrol eder
#    3) cloudflared ile gecici HTTPS public URL acar
#       -> ornek: https://xxxx-yyyy.trycloudflare.com
#    4) URL'yi panoya kopyalar + ekrana yazar
#    5) https://pwabuilder.com adresini tarayicida acar
#
#  Sen yapacaklarin:
#    A) URL'yi PWABuilder'in "Enter URL" kutusuna yapistir
#    B) Start -> Package For Stores -> Android -> Generate Package
#    C) Indirilen ZIP icinden APK'yi al
#    D) Bu pencereyi kapat (tunnel durur)
#
#  ON KOSUL: QuantDashboard.exe veya 'python launcher.py' calisiyor olmali.
# =============================================================================

$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$TOOLS = Join-Path $ROOT "tools"
$CLOUDFLARED = Join-Path $TOOLS "cloudflared.exe"
$PWA_PORT = 8502
$DASHBOARD_PORT = 8501

Write-Host ""
Write-Host "+--------------------------------------------------------+" -ForegroundColor Cyan
Write-Host "|  Quant AI Dashboard  -  APK Olusturma Yardimcisi       |" -ForegroundColor Cyan
Write-Host "+--------------------------------------------------------+" -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------------------------------------
# 1) PWA server kontrol (port 8502)
# -----------------------------------------------------------------------------
Write-Host "[1/4] PWA sunucusu kontrol ediliyor (port $PWA_PORT)..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:$PWA_PORT/health" -UseBasicParsing -TimeoutSec 3
    if ($health.StatusCode -eq 200) {
        Write-Host "      OK - PWA server canli" -ForegroundColor Green
    }
} catch {
    Write-Host "      HATA - Port $PWA_PORT cevap vermiyor!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Cozum: Once 'QuantDashboard.exe' (veya 'python launcher.py')" -ForegroundColor Yellow
    Write-Host "         calistir. Konsolda 'PWA server baslatildi' gormeli." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  ENTER ile cik"
    exit 1
}

# -----------------------------------------------------------------------------
# 2) cloudflared.exe varsa kullan, yoksa indir
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/4] cloudflared.exe kontrol ediliyor..." -ForegroundColor Yellow
if (-not (Test-Path $TOOLS)) {
    New-Item -ItemType Directory -Force -Path $TOOLS | Out-Null
}

if (-not (Test-Path $CLOUDFLARED)) {
    Write-Host "      Bulunamadi - indiriliyor (~20 MB, ilk seferlik)..." -ForegroundColor Yellow
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $url -OutFile $CLOUDFLARED -UseBasicParsing
        Write-Host "      OK - indirildi: $CLOUDFLARED" -ForegroundColor Green
    } catch {
        Write-Host "      HATA - indirme basarisiz: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "  Manuel indir: $url" -ForegroundColor Yellow
        Write-Host "  Sonra $CLOUDFLARED konumuna kopyala." -ForegroundColor Yellow
        Read-Host "  ENTER ile cik"
        exit 1
    }
} else {
    Write-Host "      OK - hazir: $CLOUDFLARED" -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# 3) Cloudflare Tunnel ac
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/4] Public HTTPS tunnel aciliyor..." -ForegroundColor Yellow
Write-Host "      Bu pencereyi KAPATMA - APK uretene kadar acik kalsin." -ForegroundColor Yellow
Write-Host ""

$logFile = Join-Path $env:TEMP "cloudflared-quant-$(Get-Date -Format 'yyyyMMddHHmmss').log"
$proc = Start-Process -FilePath $CLOUDFLARED `
    -ArgumentList @("tunnel", "--url", "http://localhost:$PWA_PORT", "--no-autoupdate") `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError "$logFile.err" `
    -NoNewWindow `
    -PassThru

Write-Host "      Tunnel baslatildi (PID: $($proc.Id))" -ForegroundColor Green
Write-Host "      URL bekleniyor (15 saniye max)..." -ForegroundColor Gray

$publicUrl = $null
$urlPattern = 'https://[a-z0-9-]+\.trycloudflare\.com'
$startTime = Get-Date

while (((Get-Date) - $startTime).TotalSeconds -lt 30 -and -not $publicUrl) {
    Start-Sleep -Milliseconds 800
    foreach ($f in @($logFile, "$logFile.err")) {
        if (Test-Path $f) {
            $content = Get-Content $f -Raw -ErrorAction SilentlyContinue
            if ($content -and ($content -match $urlPattern)) {
                $publicUrl = $matches[0]
                break
            }
        }
    }
}

if (-not $publicUrl) {
    Write-Host ""
    Write-Host "      HATA - URL alinamadi (zaman asimi)" -ForegroundColor Red
    Write-Host "      Log: $logFile" -ForegroundColor Gray
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Read-Host "      ENTER ile cik"
    exit 1
}

# -----------------------------------------------------------------------------
# 4) URL'yi panoya + tarayiciya
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/4] HAZIR!" -ForegroundColor Green
Write-Host ""
Write-Host "  +--------------------------------------------------+" -ForegroundColor Cyan
Write-Host "  |  Public HTTPS URL (PWABuilder'a yapistir):       |" -ForegroundColor Cyan
Write-Host "  +--------------------------------------------------+" -ForegroundColor Cyan
Write-Host ""
Write-Host "    $publicUrl" -ForegroundColor White -BackgroundColor DarkBlue
Write-Host ""

try {
    Set-Clipboard -Value $publicUrl
    Write-Host "  [OK] URL panoya kopyalandi - Ctrl+V ile yapistirabilirsin" -ForegroundColor Green
} catch {
    Write-Host "  Pano erisilemedi - URL'yi elle kopyala" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  ADIMLAR:" -ForegroundColor Yellow
Write-Host "    1) Acilan tarayicida URL kutusuna URL'yi yapistir (Ctrl+V)" -ForegroundColor White
Write-Host "    2) 'Start' -> manifest/SW kontrolu (yesil olmali)" -ForegroundColor White
Write-Host "    3) 'Package For Stores' -> 'Android' -> 'Generate'" -ForegroundColor White
Write-Host "    4) Inen ZIP icinden .apk dosyasini telefona yolla" -ForegroundColor White
Write-Host "    5) Telefon: Bilinmeyen uygulamalara izin -> kur" -ForegroundColor White
Write-Host ""
Write-Host "  APK URETIMI BITTIGINDE BU PENCEREYI KAPAT" -ForegroundColor Magenta
Write-Host "  (kapatinca tunnel durur - APK URL'si calismaz olur)" -ForegroundColor Magenta
Write-Host ""

# Tarayicida PWABuilder'i ac
Start-Sleep -Seconds 1
$builderUrl = "https://www.pwabuilder.com/?site=" + [uri]::EscapeDataString($publicUrl)
try {
    Start-Process $builderUrl
    Write-Host "  Tarayici aciliyor: PWABuilder.com" -ForegroundColor Green
} catch {
    Write-Host "  Tarayici manuel ac: $builderUrl" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Tunnel log: $logFile" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  [Ctrl+C veya pencereyi kapat = tunnel durur]" -ForegroundColor DarkGray
Write-Host ""

# Tunnel'i ayakta tut (kullanici Ctrl+C basana kadar)
try {
    Wait-Process -Id $proc.Id
} catch {
    Write-Host "  Tunnel durdu." -ForegroundColor Yellow
}
