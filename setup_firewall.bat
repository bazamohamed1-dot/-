@echo off
chcp 65001 >nul
echo جاري فتح المنفذ 8000 في جدار الحماية...
echo يرجى تشغيل هذا الملف كمسؤول (Run as Administrator)

netsh advfirewall firewall show rule name="BazaSchool" >nul
if %errorlevel%==0 (
    echo المنفذ مفتوح مسبقاً.
) else (
    netsh advfirewall firewall add rule name="BazaSchool" dir=in action=allow protocol=TCP localport=8000
    echo تم فتح المنفذ 8000 بنجاح!
)

pause
