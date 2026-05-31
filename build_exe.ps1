# build_exe.ps1 - QuantDashboard.exe tek dosya derleyici
# Kullanim: .\build_exe.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$pip          = ".\venv\Scripts\pip.exe"
$python       = ".\venv\Scripts\python.exe"
$pyinstaller  = ".\venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $python)) {
    Write-Host "HATA: venv yok. Once .\setup.ps1 calistir." -ForegroundColor Red
    exit 1
}

Write-Host "[1/4] PyInstaller kuruluyor..." -ForegroundColor Cyan
& $pip install --upgrade pyinstaller pyinstaller-hooks-contrib | Out-Null

if (-not (Test-Path $pyinstaller)) {
    Write-Host "HATA: pyinstaller kurulamadi." -ForegroundColor Red
    exit 1
}

Write-Host "[2/4] Eski build temizleniyor..." -ForegroundColor Cyan
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "[3/4] EXE derleniyor (10-25 dakika surebilir)..." -ForegroundColor Cyan
Write-Host "      Konsolu kapatma! Prophet/XGBoost icin ~3GB RAM kullanir."
Write-Host ""

$startTime = Get-Date
& $pyinstaller QuantDashboard.spec --noconfirm --clean
$elapsed = (Get-Date) - $startTime

Write-Host ""
Write-Host "[4/4] Sonuc:" -ForegroundColor Green

$exePath = "dist\QuantDashboard.exe"
if (Test-Path $exePath) {
    $sizeMB = [Math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "  EXE: $exePath ($sizeMB MB)" -ForegroundColor Green
    Write-Host "  Sure: $($elapsed.ToString('mm\:ss'))" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Arkadasa GONDER:" -ForegroundColor Yellow
    Write-Host "    1) dist\QuantDashboard.exe" -ForegroundColor White
    Write-Host "    2) KURULUM_ARKADAS.md" -ForegroundColor White
    Write-Host ""
    Write-Host "  Test icin:" -ForegroundColor Yellow
    Write-Host "    .\dist\QuantDashboard.exe" -ForegroundColor White
} else {
    Write-Host "  HATA: EXE olusturulamadi!" -ForegroundColor Red
    Write-Host "  Build loglari: build\QuantDashboard\warn-QuantDashboard.txt" -ForegroundColor Yellow
    exit 1
}
