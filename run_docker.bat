@echo off
setlocal

echo ========================================================
echo       Baza Systems - Docker Start Script
echo ========================================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running. Please start Docker Desktop and try again.
    pause
    exit /b
)

echo [1/3] Building and Starting Services...
docker-compose up -d --build

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start services. Check Docker logs.
    pause
    exit /b
)

echo.
echo [2/3] Checking Service Status...
docker-compose ps

echo.
echo [3/3] Following Logs (Press Ctrl+C to stop viewing logs, Server will keep running)...
echo.
docker-compose logs -f
