# setup.ps1 - Ilk kurulum (venv + pip + NLTK)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

# Python bul
$py = $null
foreach ($p in @(
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe",
    "C:\Program Files\Python312\python.exe"
)) {
    if (Test-Path $p) { $py = $p; break }
}
if (-not $py) {
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $py -or $py -match "WindowsApps") {
    Write-Host "HATA: Python bulunamadi. winget install Python.Python.3.12" -ForegroundColor Red
    exit 1
}
Write-Host "Python: $py" -ForegroundColor Green

# venv
if (-not (Test-Path "venv")) {
    & $py -m venv venv
    Write-Host "venv olusturuldu" -ForegroundColor Green
}

$pip = Join-Path $here "venv\Scripts\pip.exe"
$pythonVenv = Join-Path $here "venv\Scripts\python.exe"

& $pip install --upgrade pip
& $pip install -r requirements.txt

Write-Host "NLTK verileri indiriliyor..." -ForegroundColor Yellow
& $pythonVenv -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True); nltk.download('brown', quiet=True)"
& $pythonVenv -c "from textblob import TextBlob; TextBlob('test').sentiment"

Write-Host ""
Write-Host "Kurulum tamam. Calistirmak icin:" -ForegroundColor Cyan
Write-Host "  .\run.bat" -ForegroundColor White
