@echo off
setlocal

:: This script starts the local server using waitress for testing.
:: Ensure you have installed requirements.txt first.

echo.
echo Starting School Management Server...
echo.

:: Migrate Database
python manage.py migrate

:: Collect Static Files (optional in local dev but good practice)
python manage.py collectstatic --noinput

:: Start Waitress Server (Correct Syntax)
echo Server is running at http://localhost:8000
waitress-serve --port=8000 School_Management.wsgi:application
pause
