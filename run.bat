@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\streamlit.exe" (
    echo venv yok - once setup.ps1 calistir:
    echo   powershell -ExecutionPolicy Bypass -File setup.ps1
    pause
    exit /b 1
)
echo Quant AI Dashboard baslatiliyor...
echo Tarayici: http://localhost:8501
echo Kapatmak icin bu pencerede Ctrl+C
echo.
call venv\Scripts\activate.bat
streamlit run app.py
pause
