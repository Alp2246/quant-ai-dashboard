@echo off
REM ============================================================
REM deploy_to_oracle.bat - PC'den Oracle sunucuya dosya yolla
REM
REM Ilk kurulum sonrasi GUNCELLEMELERI deploy etmek icin kullan.
REM Sadece degisen dosyalari yollar (rsync delta sync).
REM ============================================================
setlocal enabledelayedexpansion

REM ---------- KONFIG ----------
set SERVER_IP=
set SERVER_USER=ubuntu
set KEY_FILE=%USERPROFILE%\.ssh\quantai.key
set REMOTE_DIR=/home/ubuntu/quant-dashboard
set LOCAL_DIR=%~dp0..

REM Config'i config.ini'den oku (varsa)
if exist "%~dp0server_config.ini" (
    for /f "tokens=1,2 delims==" %%a in (%~dp0server_config.ini) do (
        if "%%a"=="SERVER_IP" set SERVER_IP=%%b
        if "%%a"=="SERVER_USER" set SERVER_USER=%%b
        if "%%a"=="KEY_FILE" set KEY_FILE=%%b
    )
)

if "%SERVER_IP%"=="" (
    echo.
    echo Sunucu IP adresi ayarlanmamis.
    echo.
    set /p SERVER_IP="Oracle sunucu Public IP adresi: "
    echo.
    echo Bu IP'yi kaydetmek icin %~dp0server_config.ini olusturuluyor...
    (
        echo SERVER_IP=!SERVER_IP!
        echo SERVER_USER=%SERVER_USER%
        echo KEY_FILE=%KEY_FILE%
    ) > "%~dp0server_config.ini"
)

if not exist "%KEY_FILE%" (
    echo HATA: SSH key bulunamadi: %KEY_FILE%
    echo Oracle Console'dan indirip su yere koy: %KEY_FILE%
    exit /b 1
)

echo.
echo ============================================================
echo  DEPLOY: %LOCAL_DIR% -^> %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%
echo ============================================================
echo.

REM Test SSH connection
echo [1/4] SSH baglanti testi...
ssh -i "%KEY_FILE%" -o ConnectTimeout=10 -o StrictHostKeyChecking=no %SERVER_USER%@%SERVER_IP% "echo OK" >nul 2>&1
if errorlevel 1 (
    echo HATA: SSH baglanti basarisiz
    echo Kontrol et: ssh -i "%KEY_FILE%" %SERVER_USER%@%SERVER_IP%
    exit /b 1
)
echo     OK

REM Rsync ile gonder (Windows 10/11'de native scp - rsync benzeri)
echo.
echo [2/4] Dosyalar yollanan kontrol...

REM rsync varsa kullan (WSL/Git Bash icinden) - yoksa scp
where rsync >nul 2>&1
if not errorlevel 1 (
    echo     rsync kullaniliyor...
    rsync -avz --delete ^
        --exclude="venv/" ^
        --exclude="__pycache__/" ^
        --exclude=".pytest_cache/" ^
        --exclude="*.pyc" ^
        --exclude="data/state/" ^
        --exclude="data/logs/" ^
        --exclude=".env" ^
        --exclude=".git/" ^
        --exclude="node_modules/" ^
        --exclude="*.log" ^
        -e "ssh -i %KEY_FILE% -o StrictHostKeyChecking=no" ^
        "%LOCAL_DIR%/" %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
) else (
    echo     scp kullaniliyor (rsync yok)...
    scp -i "%KEY_FILE%" -o StrictHostKeyChecking=no -r ^
        "%LOCAL_DIR%\*.py" ^
        "%LOCAL_DIR%\*.md" ^
        "%LOCAL_DIR%\requirements.txt" ^
        %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
    scp -i "%KEY_FILE%" -o StrictHostKeyChecking=no -r ^
        "%LOCAL_DIR%\alpha_engine" ^
        "%LOCAL_DIR%\deploy" ^
        "%LOCAL_DIR%\data" ^
        %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
)

if errorlevel 1 (
    echo HATA: Dosya transfer basarisiz
    exit /b 1
)
echo     OK

REM Servisleri restart et
echo.
echo [3/4] Sunucuda servisleri restart et...
ssh -i "%KEY_FILE%" -o StrictHostKeyChecking=no %SERVER_USER%@%SERVER_IP% ^
    "sudo systemctl restart streamlit alpha-engine && sleep 2 && sudo systemctl is-active streamlit alpha-engine"
if errorlevel 1 (
    echo UYARI: Servis restart basarisiz - manuel kontrol et
)

REM Health check
echo.
echo [4/4] Health check...
ssh -i "%KEY_FILE%" -o StrictHostKeyChecking=no %SERVER_USER%@%SERVER_IP% ^
    "tailscale funnel status 2>/dev/null && echo --- && tail -5 /home/ubuntu/quant-dashboard/alpha_engine/data/heartbeat.txt 2>/dev/null"

echo.
echo ============================================================
echo  DEPLOY TAMAMLANDI
echo ============================================================
echo URL: https://abozer.tail4ea368.ts.net
echo ============================================================
echo.
endlocal
