# =============================================================================
#  install_autostart.ps1  --  Windows acilinca otomatik baslat
# =============================================================================
#  Calistir (NORMAL kullanici - admin gerekmez):
#    powershell -ExecutionPolicy Bypass -File install_autostart.ps1
#
#  Ne yapar?
#    1) start_dashboard.bat icin kisayol olusturur
#    2) Kisayoyu Windows Baslangic klasorune koyar
#    3) Boylece her oturum acilinca otomatik baslar
# =============================================================================

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$batPath = Join-Path $ROOT "start_dashboard.bat"

if (-not (Test-Path $batPath)) {
    Write-Host "HATA: start_dashboard.bat bulunamadi: $batPath" -ForegroundColor Red
    exit 1
}

$startupDir = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startupDir "QuantAI Dashboard.lnk"

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnkPath)
$sc.TargetPath = $batPath
$sc.WorkingDirectory = $ROOT
$sc.WindowStyle = 7  # minimized
$sc.Description = "Quant AI Dashboard - kalici URL: https://abozer.tail4ea368.ts.net"
$sc.Save()

Write-Host ""
Write-Host "=== TAMAM ===" -ForegroundColor Green
Write-Host "Kisayolu olusturuldu:" -ForegroundColor White
Write-Host "  $lnkPath" -ForegroundColor Yellow
Write-Host ""
Write-Host "Windows her acilisinda otomatik baslayacak." -ForegroundColor Green
Write-Host ""
Write-Host "Manuel calistir: start_dashboard.bat (cift tik)"
Write-Host "Kaldir         : Startup klasorunden 'QuantAI Dashboard.lnk' sil"
Write-Host ""

# Startup klasorunu ac (kullanici gorsun)
explorer.exe $startupDir
