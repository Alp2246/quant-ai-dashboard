@echo off
REM Alpha engine - her zaman proje venv Python'u ile calisir
cd /d "%~dp0"
set PY=%~dp0..\venv\Scripts\python.exe
if not exist "%PY%" (
    echo HATA: venv bulunamadi: %PY%
    echo Once: cd ..\  &&  python -m venv venv  &&  venv\Scripts\pip install -r alpha_engine\requirements.txt
    pause
    exit /b 1
)
"%PY%" -m pip install -q -r requirements.txt 2>nul
"%PY%" main.py %*
