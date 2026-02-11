@echo off
chcp 65001 >nul
title Create Director Account
color 0B

echo ========================================================
echo       Create New Director Account
echo ========================================================
echo.

:: Check for Venv
if not exist "venv" (
    echo [ERROR] Virtual Environment not found. Run run_school.bat first.
    pause
    exit /b
)

call venv\Scripts\activate

python manage.py create_director

echo.
pause
