@echo off
setlocal

echo ========================================================
echo       Baza Systems - Cloudflare Tunnel Setup (Fix)
echo ========================================================
echo.
echo Tunnel ID: 2d9d29d3-e0a0-444a-a3f7-529b660531a6
echo.

:: Ensure destination folder exists
if not exist "cloudflared" mkdir "cloudflared"

:: Check for credentials in user profile (standard location)
if not exist "%USERPROFILE%\.cloudflared\2d9d29d3-e0a0-444a-a3f7-529b660531a6.json" (
    echo [ERROR] Credential file not found in %USERPROFILE%\.cloudflared\
    echo Please make sure you have run 'cloudflared tunnel login' and created the tunnel properly.
    echo.
    echo If you have the JSON file elsewhere, please copy it manually to the 'cloudflared' folder inside this project.
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
cloudflared tunnel route dns baza-tunnel admin.bazasystems.com || echo DNS route might already exist or needs manual setup.

echo.
echo [SUCCESS] Setup Complete!
echo.
echo IMPORTANT: To apply the fix, please restart Docker:
echo 1. docker-compose down
echo 2. docker-compose up -d --build
echo.
pause
