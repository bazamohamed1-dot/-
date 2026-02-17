@echo off
setlocal EnableDelayedExpansion

echo ========================================================
echo       Baza Systems - Docker Start Script
echo ========================================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Docker is not running. Please start Docker Desktop and try again.
    pause
    exit /b
)

:: Check if Port 8000 is occupied
netstat -ano | find "LISTENING" | find ":8000 " >nul
if !errorlevel! equ 0 (
    echo [WARNING] Port 8000 is currently in use.
    echo Attempting to stop existing docker containers...
    docker-compose -p baza-project down

    :: Check again after stopping containers
    timeout /t 3 /nobreak >nul
    netstat -ano | find "LISTENING" | find ":8000 " >nul
    if !errorlevel! equ 0 (
        echo.
        echo [ERROR] Port 8000 is still occupied by another program!
        echo It is likely 'run_school.bat' (Python) or another server.
        echo.
        echo [ARABIC] المنفذ 8000 مشغول ببرنامج آخر (مثل run_school.bat). هل تريد إغلاقه؟
        echo.
        set /p kill_proc="Do you want to automatically close the conflicting program? (Y/N): "
        if /i "!kill_proc!"=="Y" (
            echo Closing conflicting process...
            for /f "tokens=5" %%a in ('netstat -ano ^| find "LISTENING" ^| find ":8000 "') do (
                taskkill /PID %%a /F >nul 2>&1
            )
            echo Done.
        ) else (
            echo Please close the program manually and try again.
            pause
            exit /b
        )
    )
)

echo [1/3] Building and Starting Services...
docker-compose -p baza-app up -d --build

if !errorlevel! neq 0 (
    echo [ERROR] Failed to start services. Check Docker logs.
    pause
    exit /b
)

echo.
echo [2/3] Checking Service Status...
docker-compose -p baza-app ps

echo.
echo [3/3] Following Logs (Press Ctrl+C to stop viewing logs, Server will keep running)...
echo.
docker-compose -p baza-app logs -f

:: Pause at the end to keep window open if logs command exits
pause
