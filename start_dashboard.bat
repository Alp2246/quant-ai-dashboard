@echo off
REM Quant AI Dashboard - tek tik baslatici
REM Mantik: Streamlit 8501 + Tailscale Funnel 8501 (dogrudan, gateway YOK)
REM Sebep: Gateway (HTTP-only proxy) Streamlit WebSocket'i geciremiyor -> siyah ekran.
REM Tailscale Funnel WebSocket'leri dogru geciriyor.

cd /d "%~dp0"

echo ===========================================
echo   Quant AI Dashboard baslatiliyor
echo   PC      : http://localhost:8501
echo   Telefon : https://abozer.tail4ea368.ts.net
echo ===========================================

REM Eski instance varsa temizle (cakisma olmasin)
echo Eski process'ler temizleniyor...
taskkill /F /IM streamlit.exe >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8501 :8502"') do taskkill /F /PID %%p >nul 2>&1
timeout /t 2 /nobreak >nul

REM 1) Streamlit (8501) - dogrudan
echo Streamlit baslatiliyor (port 8501)...
start "Streamlit" /MIN "%~dp0venv\Scripts\streamlit.exe" run app.py ^
    --server.port 8501 ^
    --server.address 0.0.0.0 ^
    --server.headless true ^
    --server.runOnSave false ^
    --server.fileWatcherType none ^
    --server.enableStaticServing true ^
    --server.enableCORS false ^
    --server.enableXsrfProtection false ^
    --browser.serverAddress abozer.tail4ea368.ts.net ^
    --browser.serverPort 443 ^
    --browser.gatherUsageStats false
timeout /t 10 /nobreak >nul

REM 2) Tailscale Funnel -> 8501 (DOGRUDAN, WebSocket destekli)
echo Tailscale Funnel baslatiliyor (8501)...
"C:\Program Files\Tailscale\tailscale.exe" funnel reset >nul 2>&1
timeout /t 1 /nobreak >nul
"C:\Program Files\Tailscale\tailscale.exe" funnel --bg 8501 >nul 2>&1

echo.
echo ===========================================
echo   HAZIR
echo   PC      : http://localhost:8501
echo   Telefon : https://abozer.tail4ea368.ts.net
echo   APK     : C:\Users\oalpe\Desktop\QuantAI.apk
echo ===========================================
echo.
echo Bu pencereyi KAPATMA.
echo.
pause
