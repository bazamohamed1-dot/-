@echo off
setlocal

echo ========================================================
echo       Baza Systems - Cloudflare Tunnel Setup
echo ========================================================
echo.
echo Please ensure that 'cloudflared' has been installed and you have
echo already logged in once to generate the credentials.
echo.
echo Tunnel ID: 2d9d29d3-e0a0-444a-a3f7-529b660531a6
echo.

:: Check for credentials in user profile (standard location)
if not exist "%USERPROFILE%\.cloudflared\2d9d29d3-e0a0-444a-a3f7-529b660531a6.json" (
    echo [ERROR] Credential file not found in %USERPROFILE%\.cloudflared\
    echo Please make sure you have run 'cloudflared tunnel login' and created the tunnel properly.
    pause
    exit /b
)

echo [1/2] Copying credentials to project folder...
copy "%USERPROFILE%\.cloudflared\cert.pem" "cloudflared\" >nul
copy "%USERPROFILE%\.cloudflared\2d9d29d3-e0a0-444a-a3f7-529b660531a6.json" "cloudflared\" >nul

if %errorlevel% neq 0 (
    echo [ERROR] Failed to copy files. Please check permissions.
    pause
    exit /b
)

echo.
echo [2/2] Routing DNS (CNAME)...
echo We will attempt to create the DNS route for 'admin.bazasystems.com'.
cloudflared tunnel route dns baza-tunnel admin.bazasystems.com

echo.
echo [SUCCESS] Setup Complete!
echo You can now start the server with:
echo docker-compose up -d
echo.
pause
