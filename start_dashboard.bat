@echo off
REM Quant AI Dashboard - tek tik baslatici (EXE'siz)
REM Bu dosyayi Windows Baslangic klasorune koyarsan otomatik baslar.

cd /d "%~dp0"

echo ===========================================
echo   Quant AI Dashboard baslatiliyor
echo   Kalici URL: https://abozer.tail4ea368.ts.net
echo ===========================================

REM 1) Tailscale Funnel ayakta mi (yoksa baslat)
"C:\Program Files\Tailscale\tailscale.exe" funnel status >nul 2>&1
if errorlevel 1 (
    echo Tailscale Funnel baslatiliyor...
    start "" "C:\Program Files\Tailscale\tailscale.exe" funnel --bg 8501
    timeout /t 3 /nobreak >nul
)

REM 2) Streamlit dashboard baslat
echo Streamlit baslatiliyor (port 8501)...
"%~dp0venv\Scripts\streamlit.exe" run app.py ^
    --server.port 8501 ^
    --server.address 0.0.0.0 ^
    --server.headless true ^
    --server.runOnSave false ^
    --server.fileWatcherType none ^
    --browser.gatherUsageStats false
