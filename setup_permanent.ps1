# =============================================================================
#  setup_permanent.ps1  —  Kalici HTTPS + APK (Tailscale Funnel)
# =============================================================================
#  ONCE calistir (Funnel admin panelinde acildiktan SONRA):
#    cd C:\fpga_work\quant-dashboard
#    .\setup_permanent.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$TS = "C:\Program Files\Tailscale\tailscale.exe"
$PWA_PORT = 8502

Write-Host ""
Write-Host "=== Quant AI — Kalici Kurulum ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $TS)) {
    Write-Host "HATA: Tailscale kurulu degil. Once tailscale-setup.msi calistir." -ForegroundColor Red
    exit 1
}

# 1) Tailscale durumu
Write-Host "[1/5] Tailscale durumu..." -ForegroundColor Yellow
$st = & $TS status 2>&1
if ($LASTEXITCODE -ne 0 -or $st -match "Logged out") {
    Write-Host "  Giris yok. Calistir: tailscale up" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: $st" -ForegroundColor Green

# DNS adi (kalici URL)
$json = & $TS status --json 2>&1 | Out-String
$dns = $null
if ($json -match '"DNSName"\s*:\s*"([^"]+)"') {
    $dns = $Matches[1].TrimEnd('.')
}
if (-not $dns) {
    Write-Host "  DNSName alinamadi" -ForegroundColor Red
    exit 1
}
$PERMANENT_URL = "https://$dns"
Write-Host "  Kalici URL: $PERMANENT_URL" -ForegroundColor Green

# 2) PWA port
Write-Host ""
Write-Host "[2/5] PWA port $PWA_PORT..." -ForegroundColor Yellow
try {
    $h = Invoke-WebRequest "http://127.0.0.1:$PWA_PORT/health" -UseBasicParsing -TimeoutSec 3
    if ($h.StatusCode -eq 200) { Write-Host "  OK" -ForegroundColor Green }
} catch {
    Write-Host "  HATA: QuantDashboard.exe acik degil (port $PWA_PORT)" -ForegroundColor Red
    exit 1
}

# 3) Funnel ac
Write-Host ""
Write-Host "[3/5] Tailscale Funnel aciliyor..." -ForegroundColor Yellow
$funnelOut = & $TS funnel --bg $PWA_PORT 2>&1 | Out-String
if ($funnelOut -match "Funnel is not enabled") {
    Write-Host ""
    Write-Host "  FUNNEL HENUZ AKTIF DEGIL!" -ForegroundColor Red
    if ($funnelOut -match "https://login\.tailscale\.com/f/[^\s]+") {
        $enableUrl = $Matches[0]
        Write-Host "  Tarayicida ac ve Enable Funnel tikla:" -ForegroundColor Yellow
        Write-Host "  $enableUrl" -ForegroundColor White
        Start-Process $enableUrl
    }
    Write-Host ""
    Write-Host "  Enable ettikten sonra bu scripti TEKRAR calistir." -ForegroundColor Yellow
    exit 2
}
Write-Host "  $funnelOut" -ForegroundColor Green
& $TS funnel status

# 4) Public URL test
Write-Host ""
Write-Host "[4/5] Public URL test: $PERMANENT_URL/health" -ForegroundColor Yellow
Start-Sleep -Seconds 2
try {
    $pub = Invoke-WebRequest "$PERMANENT_URL/health" -UseBasicParsing -TimeoutSec 15
    Write-Host "  OK HTTP $($pub.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "  UYARI: Public erisim henuz yok ($_)" -ForegroundColor Yellow
    Write-Host "  Bir kac saniye bekle, funnel status kontrol et." -ForegroundColor Yellow
}

# 5) Kalici APK uret
Write-Host ""
Write-Host "[5/5] Kalici APK uretiliyor..." -ForegroundColor Yellow
$env:QUANT_PERMANENT_URL = $PERMANENT_URL
& "$ROOT\venv\Scripts\python.exe" "$ROOT\_build_apk_permanent.py"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  APK uretimi basarisiz" -ForegroundColor Red
    exit 1
}

# Otomatik baslatma gorevi
Write-Host ""
Write-Host "Windows baslangic gorevi ekleniyor..." -ForegroundColor Yellow
$taskName = "QuantAI-TailscaleFunnel"
$action = New-ScheduledTaskAction -Execute $TS -Argument "funnel --bg $PWA_PORT"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host "  Gorev: $taskName (oturum acilinca funnel baslar)" -ForegroundColor Green
} catch {
    Write-Host "  Gorev eklenemedi (admin?): $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== TAMAMLANDI ===" -ForegroundColor Green
Write-Host "  Kalici URL : $PERMANENT_URL"
Write-Host "  APK        : Downloads\QuantAI_PERMANENT\QuantAI-Dashboard.apk"
Write-Host ""
Write-Host "  Telefona APK kur. PC + QuantDashboard.exe acikken her yerden calisir."
Write-Host "  (Mobil veri dahil — Funnel public HTTPS)"
Write-Host ""
