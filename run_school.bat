@echo off
chcp 65001 >nul
title School Management System - Local Server
color 0A

echo ========================================================
echo       School Management System - Local Version
echo ========================================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b
)

:: Check/Create Virtual Environment
if not exist "venv" (
    echo [INFO] Creating Virtual Environment...
    python -m venv venv
)

:: Activate Virtual Environment
call venv\Scripts\activate

:: Install Dependencies (check if waitress is installed)
python -c "import waitress" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing Dependencies...
    pip install -r requirements.txt
    echo [INFO] Setup complete.
)

:: Run Migrations
echo [INFO] Checking Database...
python manage.py migrate --noinput >nul 2>&1

:: Run Static Files Collection
echo [INFO] Collecting Static Files...
python manage.py collectstatic --noinput >nul 2>&1

echo.
echo ========================================================
echo [SUCCESS] Server is Starting...
echo.

:: Get Local IP Address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4 Address"') do set IP=%%a
set IP=%IP:~1%

echo Local Access (You):     http://localhost:8000
echo LAN Access (Others):    http://%IP%:8000
echo.
echo [IMPORTANT] Ensure both devices are on the SAME WiFi network.
echo [TIP] If LAN Access fails, check Windows Firewall (Allow port 8000).
echo.
echo Press Ctrl+C to stop the server.
echo ========================================================

:: Ask for Internet Access (Tunnel)
set /p tunnel="Enable Internet Access via Cloudflare? (Y/N): "
if /i "%tunnel%"=="Y" (
    echo [INFO] Starting Cloudflare Tunnel...
    start /min cloudflared tunnel --url http://localhost:8000
    echo [INFO] Tunnel started in background. Check the popup window for the URL.
)

:: Start Waitress Server
waitress-serve --listen=*:8000 School_Management.wsgi:application

pause
