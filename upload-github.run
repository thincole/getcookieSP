@echo off
chcp 65001 >nul 2>&1
title GitHub Uploader - GemLogin Cookie Extractor
color 0a

cd /d "%~dp0"

:: Tim Python
set "PY="
python --version >nul 2>&1
if not errorlevel 1 (
    set "PY=python"
    goto :FOUND
)

for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%d\python.exe" (
        set "PY=%%d\python.exe"
        goto :FOUND
    )
)

color 0c
echo [x] Khong tim thay Python tren may!
echo [*] Vui long cai dat Python hoac chay qua run.bat truoc.
pause
exit /b

:FOUND
"%PY%" "%~dp0upload_github.py" %*

if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo.
    echo [x] Co loi trong qua trinh upload!
)

echo.
pause
