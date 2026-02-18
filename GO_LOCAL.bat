@echo off
setlocal

echo ========================================================
echo       INSTALL AND RUN (LOCAL WIFI MODE)
echo ========================================================
echo.
echo This script will set up the project on your Windows PC.
echo Please ensure you have Python installed.
echo.

:: 1. Check/Create Virtual Environment
echo [1/3] Checking Virtual Environment (venv)...
if not exist "venv" (
    echo Creating new virtual environment...
    python -m venv venv
) else (
    echo Virtual environment exists.
)

:: 2. Install Dependencies
echo.
echo [2/3] Installing/Updating Requirements...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install requirements. Check internet connection.
    pause
    exit /b
)

:: 3. Run Migration and Server
echo.
echo [3/3] Setting up Database and Server...
:: Force SQLite by explicitly setting the URL to override .env
set DATABASE_URL=sqlite:///db.sqlite3
:: Enable DEBUG to disable SSL Redirect locally
set DEBUG=True

echo Running Migrations...
python manage.py migrate

echo Collecting Static Files...
python manage.py collectstatic --noinput

echo.
echo ========================================================
echo       SETUP COMPLETE!
echo ========================================================
echo.
echo 1. From THIS PC:  http://localhost:8000
echo.
echo 2. From MOBILE (WiFi):
echo    Use the IPv4 address below with port 8000
ipconfig | findstr "IPv4"
echo    Example: http://192.168.1.5:8000
echo.

:: Start Server
echo Starting Server...
waitress-serve --port=8000 --threads=4 School_Management.wsgi:application

pause