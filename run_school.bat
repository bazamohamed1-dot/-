@echo off
REM Use OEM code page for .bat parsing reliability on French/Arabic Windows; UTF-8 only for Python.
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ==========================================
echo      School management app - Baza
echo ==========================================

REM 1. Check Virtual Environment
if exist venv goto ACTIVATE_VENV

echo [INFO] Creating Virtual Environment (First Run)...
python -m venv venv
if %errorlevel% neq 0 goto ERROR_VENV

:ACTIVATE_VENV
call venv\Scripts\activate
if %errorlevel% neq 0 goto ERROR_ACTIVATE

REM 2. Check Dependencies
echo [INFO] Checking dependencies...
pip install -r requirements.txt > nul 2>&1
if %errorlevel% equ 0 goto DJANGO_CHECK

echo [WARN] Installing missing packages...
pip install -r requirements.txt
if %errorlevel% neq 0 goto ERROR_DEPS

:DJANGO_CHECK
echo [INFO] Django system check...
python manage.py check
if %errorlevel% neq 0 goto ERROR_CHECK
goto FIREWALL_SETUP

:FIREWALL_SETUP
if exist .firewall_done goto START_APP
echo [INFO] Configuring Firewall for Network Access...
netsh advfirewall firewall add rule name="SchoolApp_8000" dir=in action=allow protocol=TCP localport=8000 > nul 2>&1
echo done > .firewall_done

:START_APP
echo [INFO] Cleaning up broken migration files if they exist...
if exist students\migrations\0020_*.py del students\migrations\0020_*.py
if exist students\migrations\0021_*.py del students\migrations\0021_*.py
if exist students\migrations\0022_*.py del students\migrations\0022_*.py

echo [INFO] Updating Database...
python manage.py makemigrations students --noinput
python manage.py migrate --noinput

echo.
echo [SUCCESS] Server Started!
echo ------------------------------------------
echo Local Access:   http://localhost:8000
echo Network Access: http://0.0.0.0:8000
echo ------------------------------------------
echo Press Ctrl+C to stop.
echo.

python manage.py runserver 0.0.0.0:8000
goto END

:ERROR_VENV
echo [ERROR] Failed to create venv. Ensure Python 3.10+ is installed.
goto ERROR_PAUSE

:ERROR_ACTIVATE
echo [ERROR] Failed to activate venv.
goto ERROR_PAUSE

:ERROR_DEPS
echo [ERROR] Failed to install dependencies. Check internet connection.
goto ERROR_PAUSE

:ERROR_CHECK
echo [ERROR] manage.py check failed. Fix settings, .env, or migrations then retry.
goto ERROR_PAUSE

:ERROR_PAUSE
pause
exit /b 1

:END
pause
