@echo off
chcp 65001 >nul 2>&1
title Cap Nhat GemLogin Cookie Extractor (Auto Updater)
color 0a

cd /d "%~dp0"

echo ========================================================
echo      CAP NHAT GEMLOGIN COOKIE EXTRACTOR TU GITHUB
echo ========================================================
echo.

:: Hien thi phien ban hien tai
set "OLD_VER=Unknown"
if exist "version.txt" (
    set /p OLD_VER=<version.txt
)
echo [*] Phien ban hien tai: v%OLD_VER%
echo [*] Dang ket noi toi GitHub (thincole/getcookieSP)...
echo.

:: 1. Sao luu config.json cua nguoi dung
if exist "config.json" (
    copy /y "config.json" "config.json.bak" >nul 2>&1
    echo [OK] Da sao luu cau hinh ca nhan (config.json).
)

:: 2. Thu cap nhat bang Git neu co .git va git
set "UPDATED_BY_GIT=0"
if exist ".git" (
    git --version >nul 2>&1
    if not errorlevel 1 (
        echo [*] Dang cap nhat qua Git...
        git fetch origin main >nul 2>&1
        git reset --hard origin/main >nul 2>&1
        if not errorlevel 1 (
            set "UPDATED_BY_GIT=1"
            echo [OK] Cap nhat qua Git thanh cong!
        )
    )
)

:: 3. Neu khong co Git hoac .git (vi du giai nen tu file ZIP), tai truc tiep tu GitHub Raw
if "%UPDATED_BY_GIT%"=="0" (
    echo [*] Dang tai cac file ban moi nhat truc tiep tu GitHub...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
        "$base = 'https://raw.githubusercontent.com/thincole/getcookieSP/main'; " ^
        "$wc = New-Object System.Net.WebClient; " ^
        "$wc.Encoding = [System.Text.Encoding]::UTF8; " ^
        "$wc.Headers.Add('Cache-Control', 'no-cache'); " ^
        "$files = @('gui.py', 'get_gemlogin_cookies.py', 'version.txt', 'run.bat', 'README.md'); " ^
        "foreach ($f in $files) { " ^
        "    Write-Host ('   -> Dang tai ' + $f + '...'); " ^
        "    $wc.DownloadFile($base + '/' + $f + '?t=' + [DateTimeOffset]::Now.ToUnixTimeSeconds(), (Join-Path '%~dp0' $f)); " ^
        "}"
    if errorlevel 1 (
        color 0c
        echo.
        echo [x] LOI: Khong the tai ban cap nhat tu GitHub! Vui long kiem tra mang Internet.
        if exist "config.json.bak" (
            copy /y "config.json.bak" "config.json" >nul 2>&1
            del "config.json.bak" >nul 2>&1
        )
        pause
        exit /b 1
    )
    echo [OK] Da tai xong tat ca file ma nguon moi nhat!
)

:: 4. Khoi phuc lai config.json cua nguoi dung
if exist "config.json.bak" (
    copy /y "config.json.bak" "config.json" >nul 2>&1
    del "config.json.bak" >nul 2>&1
    echo [OK] Da khoi phuc cau hinh ca nhan (config.json).
)

:: 5. Kiem tra va cai dat thu vien Python bo sung (psutil, websocket-client)
set "PY="
python --version >nul 2>&1
if not errorlevel 1 (
    set "PY=python"
) else (
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%d\python.exe" set "PY=%%d\python.exe"
    )
)

if defined PY (
    echo [*] Dang kiem tra thu vien Python (websocket-client, psutil)...
    "%PY%" -m pip install --user --quiet websocket-client psutil >nul 2>&1
    echo [OK] Thu vien Python da day du.
)

set "NEW_VER=Unknown"
if exist "version.txt" (
    set /p NEW_VER=<version.txt
)

echo.
echo ========================================================
echo   HOAN TAT CAP NHAT! Phien ban moi: v%NEW_VER%
echo ========================================================
echo.
set /p RUN_NOW="Ban co muon mo phan mem ngay bay gio khong? (Y/N, Enter=Y): "
if /i "%RUN_NOW%"=="" set "RUN_NOW=Y"
if /i "%RUN_NOW%"=="Y" (
    call "%~dp0run.bat"
    exit /b 0
)

pause
