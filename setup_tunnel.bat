@echo off
setlocal

echo ========================================================
echo       Baza Systems - Cloudflare Tunnel Setup
echo ========================================================
echo.

:: Check for cloudflared
where cloudflared >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] cloudflared is not installed or not in PATH.
    echo Please install the 'cloudflared-windows-amd64.msi' file included in this folder.
    echo After installation, restart this script.
    pause
    exit /b
)

echo [1/5] Authenticating with Cloudflare...
echo A browser window will open. Please log in and select 'bazasystems.com'.
cloudflared tunnel login
if %errorlevel% neq 0 (
    echo [ERROR] Login failed.
    pause
    exit /b
)

echo.
echo [2/5] Creating Tunnel 'baza-tunnel'...
:: Try to create, if exists, just ignore error (it might already exist)
cloudflared tunnel create baza-tunnel || echo Tunnel might already exist.

echo.
echo [3/5] Configuring Tunnel...
echo We need the Tunnel ID (UUID) to configure the system.
echo.
echo Here is the list of your tunnels:
cloudflared tunnel list
echo.
set /p TUNNEL_ID="Enter the ID (UUID) of 'baza-tunnel' from the list above: "

if "%TUNNEL_ID%"=="" (
    echo [ERROR] No ID entered. Exiting.
    pause
    exit /b
)

:: Create config.yml
echo Creating config.yml...
(
echo tunnel: %TUNNEL_ID%
echo credentials-file: /home/nonroot/.cloudflared/%TUNNEL_ID%.json
echo.
echo ingress:
echo   - hostname: admin.bazasystems.com
echo     service: http://web:8000
echo   - service: http_status:404
) > cloudflared\config.yml

:: Copy credentials
echo Copying credentials...
copy "%USERPROFILE%\.cloudflared\cert.pem" "cloudflared\" >nul
copy "%USERPROFILE%\.cloudflared\%TUNNEL_ID%.json" "cloudflared\" >nul

echo.
echo [4/5] Routing DNS...
cloudflared tunnel route dns baza-tunnel admin.bazasystems.com

echo.
echo [5/5] Setup Complete!
echo.
echo You can now start the server with:
echo docker-compose up -d
echo.
pause
