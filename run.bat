@echo off
chcp 65001 >nul 2>&1
title GemLogin Cookie Extractor
color 0b
echo ====================================================
echo      KHOI DONG GEMLOGIN COOKIE EXTRACTOR (GUI)
echo ====================================================
echo.
echo [*] Dang kiem tra moi truong Python...

:: Di chuyen den thu muc chua file bat
cd /d "%~dp0"

:: Tim Python
set "PY="

:: Thu tim python trong PATH
python --version >nul 2>&1
if not errorlevel 1 (
    set "PY=python"
    set "PW=pythonw"
    goto :FOUND
)

:: Thu cac duong dan mac dinh
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%d\python.exe" (
        set "PY=%%d\python.exe"
        set "PW=%%d\pythonw.exe"
        goto :FOUND
    )
)

:: Khong tim thay -> tai va cai Python
color 0e
echo [!] Khong tim thay Python! Dang tai va cai dat tu dong...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '%~dp0python_installer.exe')"
if errorlevel 1 (
    color 0c
    echo [x] LOI: Khong the tai Python! Kiem tra ket noi mang.
    pause
    exit /b
)
echo [*] Dang cai dat Python (Silent Install)...
start /wait "" "%~dp0python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del "%~dp0python_installer.exe" >nul 2>&1

:: Tim lai sau khi cai
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%d\python.exe" (
        set "PY=%%d\python.exe"
        set "PW=%%d\pythonw.exe"
        goto :FOUND
    )
)
color 0c
echo [x] LOI: Cai dat Python that bai!
echo [*] Vui long tai thu cong tu: https://python.org
pause
exit /b

:FOUND
echo [OK] Python: "%PY%"
echo.

:: Cai thu vien websocket-client neu thieu
echo [*] Kiem tra thu vien websocket-client...
"%PY%" -c "import websocket" >nul 2>&1
if errorlevel 1 (
    echo [*] Dang cai dat websocket-client...
    "%PY%" -m pip install --user websocket-client
    if errorlevel 1 (
        color 0c
        echo [x] LOI: Khong the cai websocket-client!
        echo [*] Thu chay: pip install websocket-client
        pause
        exit /b
    )
    echo [OK] Da cai xong websocket-client.
) else (
    echo [OK] websocket-client da san sang.
)
echo.

:: Kiem tra gui.py truoc khi chay
echo [*] Kiem tra gui.py...
"%PY%" -c "import sys,os; sys.path.insert(0,os.path.dirname(r'%~dp0.')); import gui" >nul 2>&1
if errorlevel 1 (
    color 0c
    echo [x] LOI khi nap gui.py! Chi tiet:
    echo ============================================
    "%PY%" -c "import sys,os; sys.path.insert(0,os.path.dirname(r'%~dp0.')); import gui"
    echo ============================================
    pause
    exit /b
)

:: Kiem tra phan mem Gemlogin
echo [*] Kiem tra phan mem Gemlogin...
tasklist /FI "IMAGENAME eq Gemlogin.exe" 2>nul | findstr /i "Gemlogin.exe" >nul
if errorlevel 1 (
    echo [!] Gemlogin chua chay. Dang tu dong khoi dong Gemlogin...
    if exist "C:\Program Files\Gemlogin\Gemlogin.exe" (
        start "" "C:\Program Files\Gemlogin\Gemlogin.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Gemlogin\Gemlogin.exe" (
        start "" "%LOCALAPPDATA%\Programs\Gemlogin\Gemlogin.exe"
    ) else if exist "%PUBLIC%\Desktop\Gemlogin.lnk" (
        start "" "%PUBLIC%\Desktop\Gemlogin.lnk"
    )
) else (
    echo [OK] Gemlogin da dang chay san.
)
echo.

:: Chay GUI
echo [*] Dang mo giao dien...
start "" "%PW%" "%~dp0gui.py"
echo [OK] Da khoi chay thanh cong!
timeout /t 3 >nul
exit
