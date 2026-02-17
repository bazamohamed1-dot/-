@echo off
setlocal

echo.
echo ========================================================
echo       START SCHOOL SERVER (LOCAL)
echo ========================================================
echo.

:: Check Virtual Environment
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] 'venv' not found. Trying global Python...
)

:: Migrate Database
echo.
echo [1/2] Checking Database...
python manage.py migrate

:: Show IP
echo.
echo [2/2] Your IP Address (for Mobile Access):
ipconfig | findstr "IPv4"
echo.
echo ========================================================
echo  Local Link: http://localhost:8000
echo  Mobile Link: http://[YOUR-IP]:8000
echo ========================================================
echo.

:: Start Waitress Server
waitress-serve --port=8000 --threads=4 School_Management.wsgi:application
pause
