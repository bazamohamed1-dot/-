@echo off
setlocal

echo.
echo ========================================================
echo       CREATE DIRECTOR ACCOUNT (LOCAL)
echo ========================================================
echo.

:: Check Virtual Environment
if not exist "venv" (
    echo [ERROR] Virtual Environment not found. Run run_school.bat first.
    pause
    exit /b
)

:: Activate Venv
call venv\Scripts\activate.bat

:: Set Local Environment
set DATABASE_URL=sqlite:///db.sqlite3
set DEBUG=True

:: Run Command
echo.
echo Please enter the details for the new Director account:
python manage.py createsuperuser

echo.
echo ========================================================
echo       ACCOUNT CREATED SUCCESSFULLY!
echo ========================================================
echo.
pause