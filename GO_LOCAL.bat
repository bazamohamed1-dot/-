@echo off
setlocal

echo ========================================================
echo       Switch to Local Mode (NO DOCKER)
echo ========================================================
echo.
echo This script will set up the local environment.
echo Please ensure you have Python installed on Windows.
echo.

:: 1. Stop Docker (Optional)
echo [1/4] Stopping Docker to save memory...
docker-compose down >nul 2>&1
taskkill /IM "Docker Desktop.exe" /F >nul 2>&1
echo Docker stopped (if it was running).

:: 2. Check/Create Virtual Environment
echo.
echo [2/4] Checking Virtual Environment (venv)...
if not exist "venv" (
    echo Creating new virtual environment...
    python -m venv venv
) else (
    echo Virtual environment exists.
)

:: 3. Install Dependencies
echo.
echo [3/4] Installing Requirements (Windows optimized)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements_local.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install requirements. Check internet connection.
    pause
    exit /b
)

:: 4. Run Migration and Server
echo.
echo [4/4] Setting up Database and Server...
:: Force SQLite by explicitly setting the URL to override .env
set DATABASE_URL=sqlite:///db.sqlite3
:: Enable DEBUG to disable SSL Redirect locally
set DEBUG=True
python manage.py migrate
python manage.py collectstatic --noinput

echo.
echo ========================================================
echo       SETUP COMPLETE!
echo ========================================================
echo.
echo You can access the site from this PC at: http://localhost:8000
echo.
echo To access from your PHONE, use the IPv4 address below:
ipconfig | findstr "IPv4"
echo.

:: Start Server
echo Starting Server...
waitress-serve --port=8000 --threads=4 School_Management.wsgi:application

pause
