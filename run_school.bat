@echo off
chcp 65001 > nul
echo ==========================================
echo      برنامج تسيير المؤسسات التربوية
echo ==========================================

REM 1. Check/Create Virtual Environment
if not exist venv (
    echo [INFO] Creating Virtual Environment (First Run)...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Ensure Python 3.10+ is installed.
        pause
        exit /b
    )
)

REM 2. Activate Environment
call venv\Scripts\activate

REM 3. Install Dependencies (Quietly check)
echo [INFO] Checking dependencies...
pip install -r requirements.txt > nul 2>&1
if errorlevel 1 (
    echo [WARN] Installing missing packages...
    pip install -r requirements.txt
)

REM 4. Setup Firewall (Once)
if not exist .firewall_done (
    echo [INFO] Configuring Firewall for Network Access...
    netsh advfirewall firewall add rule name="SchoolApp_8000" dir=in action=allow protocol=TCP localport=8000 > nul 2>&1
    echo done > .firewall_done
)

REM 5. Run Migrations
echo [INFO] Updating Database...
python manage.py migrate --noinput > nul

REM 6. Start Server
echo.
echo [SUCCESS] Server Started!
echo ------------------------------------------
echo Local Access:   http://localhost:8000
echo Network Access: http://0.0.0.0:8000
echo ------------------------------------------
echo Press Ctrl+C to stop.
echo.

python manage.py runserver 0.0.0.0:8000
pause
