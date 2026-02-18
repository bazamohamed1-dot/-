@echo off
setlocal

echo ========================================================
echo       START CLOUDFLARE TUNNEL (MANUAL)
echo ========================================================
echo.
echo ensuring cloudflared.exe exists...

if not exist "cloudflared\cloudflared.exe" (
    echo [ERROR] cloudflared.exe not found in 'cloudflared' folder.
    echo Please download it or run setup_tunnel.bat first.
    pause
    exit /b
)

echo Starting Tunnel...
echo Connect to: https://admin.bazasystems.com
echo.

cloudflared\cloudflared.exe tunnel run baza-app

pause