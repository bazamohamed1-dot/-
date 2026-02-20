@echo off
setlocal

echo ========================================================
echo       START SCHOOL MANAGEMENT SYSTEM
echo ========================================================
echo.

:: 1. Check Virtual Environment
if not exist "venv" (
    echo [1/3] First Run Detected! Setting up environment...
    echo       This may take a few minutes...
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
) else (
    echo [1/3] Environment found. Activating...
    call venv\Scripts\activate.bat
)

:: 2. Ensure Dependencies (including firebase-admin)
echo.
echo [1.5/3] Checking dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Failed to install requirements. Check internet connection.
    echo Continuing anyway...
)

:: 3. Set Environment Variables
set DATABASE_URL=sqlite:///db.sqlite3
set DEBUG=True

:: 4. Run Migrations & Checks
echo.
echo [2/3] Checking Database...
python manage.py migrate --noinput
python manage.py collectstatic --noinput

:: 5. Start Server
echo.
echo [3/3] Starting Server...
echo.
echo ========================================================
echo  ACCESS LINK: http://localhost:8000/canteen/
echo ========================================================
echo.
echo  Keep this window open to keep the system running.
echo.
echo  Opening browser automatically...
start http://localhost:8000/canteen/

waitress-serve --listen=*:8000 --threads=4 School_Management.wsgi:application
pause