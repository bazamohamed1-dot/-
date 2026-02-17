@echo off
setlocal
chcp 65001 >nul

echo.
echo ========================================================
echo       تشغيل نظام المدرسة (School Server)
echo ========================================================
echo.

:: Check Virtual Environment
if exist "venv\Scripts\activate.bat" (
    echo تفعيل البيئة الافتراضية...
    call venv\Scripts\activate
) else (
    echo [تنبيه] لم يتم العثور على 'venv'. سنحاول استخدام Python المثبت في النظام.
)

:: Migrate Database
echo.
echo [1/2] تحديث قاعدة البيانات...
python manage.py migrate

:: Show IP
echo.
echo [2/2] عنوان السيرفر (IP Address):
ipconfig | findstr "IPv4"
echo.
echo ========================================================
echo  الرابط للدخول من هذا الجهاز: http://localhost:8000
echo  الرابط للدخول من الهاتف: استخدم عنوان IPv4 الظاهر أعلاه
echo ========================================================
echo.

:: Start Waitress Server
waitress-serve --port=8000 --threads=4 School_Management.wsgi:application
pause
