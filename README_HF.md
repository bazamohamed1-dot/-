# دليل النشر على Hugging Face Spaces

للانتقال إلى Hugging Face والحصول على **16GB RAM** مجاناً، اتبع الخطوات التالية:

## 1. إنشاء مساحة جديدة (Create New Space)
1.  سجل الدخول إلى [Hugging Face](https://huggingface.co/).
2.  اضغط على صورة ملفك الشخصي -> **New Space**.
3.  **Space Name**: اختر اسماً (مثلاً `school-management`).
4.  **License**: يفضل `mit` أو `apache-2.0`.
5.  **SDK**: اختر **Docker**.
6.  **Template**: اختر **Blank**.
7.  اضغط **Create Space**.

## 2. إعداد المتغيرات (Settings)
بعد إنشاء المساحة، اذهب إلى تبويب **Settings** في الأعلى، ثم انزل إلى قسم **Variables and secrets**.
أضف المتغيرات التالية (Secrets):

| الاسم (Name) | القيمة (Value) |
|---|---|
| `SECRET_KEY` | (أي نص طويل وعشوائي للحماية) |
| `DEBUG` | `False` |
| `DATABASE_URL` | رابط قاعدة بيانات Neon الخاص بك (نفس المستخدم في Render) |
| `CLOUDINARY_CLOUD_NAME` | اسم حساب Cloudinary |
| `CLOUDINARY_API_KEY` | مفتاح Cloudinary |
| `CLOUDINARY_API_SECRET` | سر Cloudinary |
| `EMAIL_HOST_USER` | (اختياري) بريد الإدارة |

## 3. رفع الملفات
لديك خياران:
*   **الخيار السهل:** اذهب إلى تبويب **Files** في المساحة، واضغط **Add file -> Upload files**، وارفع جميع ملفات المشروع (ما عدا `.env` و `.git`).
*   **الخيار الأفضل:** اربط المستودع بـ Github أو استخدم `git push` لرفع الكود.

بمجرد رفع الملفات (خاصة `Dockerfile` الذي أنشأناه)، سيبدأ Hugging Face في بناء التطبيق تلقائياً.

## 4. تشغيل ترحيل الصور (اختياري)
بعد تشغيل التطبيق بنجاح، ولضمان تحسين الصور القديمة، يمكنك فتح "Terminal" أو "SSH" (إذا توفرت) وتشغيل:
```bash
python manage.py migrate_images
```
أو سيعمل التطبيق بشكل طبيعي وسيقوم بتحسين الصور الجديدة تلقائياً.
