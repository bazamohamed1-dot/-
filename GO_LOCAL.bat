@echo off
setlocal
chcp 65001 >nul

echo ========================================================
echo       الانتقال إلى الوضع المحلي (Local Mode Switch)
echo ========================================================
echo.
echo هذا السكربت سيقوم بإعداد بيئة العمل المحلية بدون Docker.
echo This script will set up the local environment without Docker.
echo.

:: 1. Stop Docker (Optional but recommended)
echo [1/4] محاولة إيقاف Docker لتوفير الذاكرة...
docker-compose down >nul 2>&1
taskkill /IM "Docker Desktop.exe" /F >nul 2>&1
echo تم إيقاف Docker (أو لم يكن يعمل).

:: 2. Check/Create Virtual Environment
echo.
echo [2/4] فحص البيئة الافتراضية (Python Virtual Env)...
if not exist "venv" (
    echo جاري إنشاء بيئة افتراضية جديدة...
    python -m venv venv
) else (
    echo البيئة موجودة مسبقاً.
)

:: 3. Install Dependencies
echo.
echo [3/4] تثبيت المكتبات اللازمة (Install Requirements)...
call venv\Scripts\activate
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] فشل تثبيت المكتبات. تأكد من وجود الإنترنت.
    pause
    exit /b
)

:: 4. Run Migration and Server
echo.
echo [4/4] إعداد قاعدة البيانات وتشغيل السيرفر...
python manage.py migrate
python manage.py collectstatic --noinput

echo.
echo ========================================================
echo       تم الإعداد بنجاح! (Setup Complete)
echo ========================================================
echo.
echo الآن سيتم تشغيل السيرفر.
echo يمكنك الدخول من هاتفك عبر: http://IP-ADDRESS:8000
echo (سنظهر لك عنوان IP الآن)
echo.
ipconfig | findstr "IPv4"
echo.

:: Start Server using Waitress (Production-ready for Windows)
waitress-serve --port=8000 --threads=4 School_Management.wsgi:application

pause
