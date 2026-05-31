@echo off
REM Quant AI Dashboard - otomatik guncelleme
REM Calistirinca: git pull + pip install -r requirements.txt
REM
REM Cron gibi her gun calistirmak istersen update_dashboard.bat'i Task Scheduler'a ekle.

cd /d "%~dp0"

echo ===========================================
echo   Quant AI Dashboard - Guncelleme
echo ===========================================

REM 1) Git pull (eger git repo ise)
if exist .git (
    echo [1/3] Git pull...
    git pull
) else (
    echo [1/3] Git repo degil - kod guncellemesi atlandi.
)

REM 2) Python paketleri
echo [2/3] Python paketleri kontrol...
"%~dp0venv\Scripts\pip.exe" install --upgrade -r requirements.txt --quiet

REM 3) PWA static assets yenile (ikon vb)
echo [3/3] PWA assets yenile...
if exist phone_app\generate_icons.py (
    "%~dp0venv\Scripts\python.exe" phone_app\generate_icons.py
    if not exist static\icons mkdir static\icons
    copy /Y phone_app\manifest.webmanifest static\manifest.webmanifest >nul
    copy /Y phone_app\service-worker.js static\service-worker.js >nul
    copy /Y phone_app\icons\*.png static\icons\ >nul
)

echo.
echo TAMAM - dashboard'u yeniden baslat (start_dashboard.bat)
echo.
pause
