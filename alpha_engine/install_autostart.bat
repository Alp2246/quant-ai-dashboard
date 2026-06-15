@echo off
REM Alpha Engine'i Windows baslangicina ekle - bilgisayar her acildiginda otomatik calissin
setlocal

set SRC=%~dp0start_background.vbs
set DST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\QuantAI_AlphaEngine.vbs

if not exist "%SRC%" (
    echo HATA: start_background.vbs bulunamadi
    exit /b 1
)

copy /Y "%SRC%" "%DST%" >nul
if errorlevel 1 (
    echo HATA: Kopyalanamadi: %DST%
    exit /b 1
)

echo.
echo OK Alpha Engine artik Windows acilisinda otomatik baslayacak.
echo    Konum: %DST%
echo.
echo Hemen baslat:
echo    cscript //nologo "%DST%"
echo.
echo Kaldirmak icin: del "%DST%"
echo.
pause
