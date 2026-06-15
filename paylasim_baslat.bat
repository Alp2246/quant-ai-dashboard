@echo off
chcp 65001 >nul
cd /d "%~dp0"
set TS=C:\Program Files\Tailscale\tailscale.exe
set PY=%~dp0venv\Scripts\python.exe
set ST=%~dp0venv\Scripts\streamlit.exe

echo.
echo  ============================================================
echo    QuantAI - PC Uzerinden Paylasim (arkadaslar icin)
echo  ============================================================
echo.

if not exist "%ST%" (
    echo HATA: venv yok. Once setup.ps1 veya:
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "%TS%" (
    echo UYARI: Tailscale yok - sadece yerel WiFi agi calisir.
    echo Indir: https://tailscale.com/download/windows
    goto nosts
)

"%TS%" status >nul 2>&1
if errorlevel 1 (
    echo Tailscale giris gerekli. Calistir: tailscale up
    pause
)

:nosts
echo [1/4] Eski process temizleniyor...
taskkill /F /IM streamlit.exe >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8501"') do taskkill /F /PID %%p >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/4] Streamlit baslatiliyor (port 8501)...
start "QuantAI Streamlit" /MIN "%ST%" run app.py ^
    --server.port=8501 ^
    --server.address=0.0.0.0 ^
    --server.headless=true ^
    --server.enableCORS=false ^
    --server.enableXsrfProtection=false ^
    --browser.serverAddress=abozer.tail4ea368.ts.net ^
    --browser.serverPort=443 ^
    --browser.gatherUsageStats=false
timeout /t 12 /nobreak >nul

echo [3/4] Alpha Engine (Telegram uyari) baslatiliyor...
if exist "%PY%" if exist "alpha_engine\main.py" (
    start "QuantAI Alpha" /MIN "%PY%" alpha_engine\main.py --tick 60
) else (
    echo      Alpha Engine atlandi.
)

if exist "%TS%" (
    echo [4/4] Tailscale Funnel - internet paylasimi...
    "%TS%" funnel reset >nul 2>&1
    timeout /t 1 /nobreak >nul
    "%TS%" funnel --bg 8501
    echo.
    "%TS%" funnel status 2>nul
)

echo.
echo  ============================================================
echo    HAZIR - Arkadaslarina bu linki gonder:
echo.
echo    https://abozer.tail4ea368.ts.net
echo.
echo    Senin PC (yerel):  http://localhost:8501
echo.
echo    NOT: Bu pencereyi ve PC'yi KAPATMA.
echo    NOT: Arkadaslar Tailscale hesabi GEREKMEZ (Funnel acik olmali).
echo  ============================================================
echo.
start http://localhost:8501
pause
