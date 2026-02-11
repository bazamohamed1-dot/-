@echo off
chcp 65001 >nul
title School Management System - Clean Photos
color 0C

echo ========================================================
echo       WARNING: DELETE ALL STUDENT PHOTOS
echo ========================================================
echo.
echo This tool will remove all photos from the database and disk.
echo Use this if you are experiencing errors in Student Management.
echo.

:: Check for Venv
if not exist "venv" (
    echo [ERROR] Virtual Environment not found. Run run_school.bat first.
    pause
    exit /b
)

call venv\Scripts\activate

python manage.py fix_photos

echo.
pause
