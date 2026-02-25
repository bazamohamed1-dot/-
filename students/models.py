from django.db import models
from datetime import date
from django.contrib.auth.models import User
import os
from django.conf import settings

def student_photo_path(instance, filename):
    # Extract extension or default to .jpg
    ext = os.path.splitext(filename)[1]
    if not ext:
        ext = '.jpg'

    # Sanitize ID for filename (Replace slashes and backslashes)
    safe_id = str(instance.student_id_number).replace('/', '_').replace('\\', '_').strip()

    # Return path: students_photos/{student_id}{ext}
    return f'students_photos/{safe_id}{ext}'

class Student(models.Model):
    student_id_number = models.CharField(max_length=16, unique=True, verbose_name="رقم التعريف")
    last_name = models.CharField(max_length=100, verbose_name="اللقب")
    first_name = models.CharField(max_length=100, verbose_name="الاسم")
    gender = models.CharField(max_length=10, verbose_name="الجنس")
    date_of_birth = models.DateField(verbose_name="تاريخ الميلاد")
    place_of_birth = models.CharField(max_length=100, verbose_name="مكان الميلاد")
    academic_year = models.CharField(max_length=20, verbose_name="المستوى") # مثال: أولى
    class_name = models.CharField(max_length=20, verbose_name="القسم") # مثال: أولى 1
    attendance_system = models.CharField(max_length=50, verbose_name="نظام التمدرس")
    enrollment_number = models.CharField(max_length=50, verbose_name="رقم القيد")
    enrollment_date = models.DateField(verbose_name="تاريخ التسجيل")
    exit_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الخروج")
    guardian_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="اسم الولي")
    mother_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="لقب واسم الأم")
    address = models.TextField(null=True, blank=True, verbose_name="عنوان السكن")
    guardian_phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="رقم هاتف الولي")
    photo = models.ImageField(upload_to=student_photo_path, null=True, blank=True, verbose_name="الصورة")

    def save(self, *args, **kwargs):
        # Handle Force Photo Replacement and Renaming
        if self.pk:
            try:
                old = Student.objects.get(pk=self.pk)

                # Case 1: Photo Replacement (Delete old file)
                if old.photo and self.photo and old.photo != self.photo:
                    if os.path.isfile(old.photo.path):
                        try: os.remove(old.photo.path)
                        except: pass

                # Case 2: ID Change (Rename old file to match new ID)
                if old.student_id_number != self.student_id_number and self.photo:
                    # Rename only if the photo file itself hasn't changed (or if it has, upload_to handles it)
                    # This logic primarily handles keeping the file sync if we just change ID.
                    if old.photo == self.photo and os.path.isfile(old.photo.path):
                        old_path = old.photo.path
                        root, ext = os.path.splitext(old_path)

                        # New name logic: students_photos/{new_id}{ext}
                        safe_id = str(self.student_id_number).replace('/', '_').replace('\\', '_').strip()
                        new_name = f'students_photos/{safe_id}{ext}'
                        new_full_path = os.path.join(settings.MEDIA_ROOT, new_name)

                        try:
                            # Ensure directory exists
                            os.makedirs(os.path.dirname(new_full_path), exist_ok=True)

                            os.rename(old_path, new_full_path)
                            # Update the field to point to the new name relative to MEDIA_ROOT
                            self.photo.name = new_name
                        except OSError as e:
                            print(f"Error renaming photo: {e}")

            except Student.DoesNotExist:
                pass

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "تلميذ"
        verbose_name_plural = "التلاميذ"

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

class CanteenAttendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="التلميذ")
    date = models.DateField(default=date.today, verbose_name="التاريخ")
    time = models.TimeField(auto_now_add=True, verbose_name="الوقت")

    class Meta:
        verbose_name = "حضور المطعم"
        verbose_name_plural = "سجل حضور المطعم"
        unique_together = ('student', 'date')

    def __str__(self):
        return f"{self.student} - {self.date}"

class LibraryLoan(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="التلميذ")
    book_title = models.CharField(max_length=200, verbose_name="عنوان الكتاب")
    loan_date = models.DateField(default=date.today, verbose_name="تاريخ الإعارة")
    loan_time = models.TimeField(auto_now_add=True, verbose_name="وقت الإعارة", null=True, blank=True)
    expected_return_date = models.DateField(verbose_name="تاريخ الإرجاع المحدد")
    is_returned = models.BooleanField(default=False, verbose_name="تم الإرجاع")
    actual_return_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الإرجاع الفعلي")

    class Meta:
        verbose_name = "إعارة كتاب"
        verbose_name_plural = "إعارات الكتب"

    def __str__(self):
        return f"{self.student} - {self.book_title}"

class SchoolSettings(models.Model):
    name = models.CharField(max_length=200, null=True, blank=True, verbose_name="اسم المؤسسة")
    academic_year = models.CharField(max_length=50, null=True, blank=True, verbose_name="السنة الدراسية")
    director_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="اسم المدير")
    logo = models.ImageField(upload_to='school_logo/', null=True, blank=True, verbose_name="شعار المؤسسة")
    loan_limit = models.IntegerField(default=2, verbose_name="الحد الأقصى للإعارات")
    loan_limits_by_level = models.JSONField(default=dict, blank=True, verbose_name="حدود الإعارة حسب المستوى")
    admin_email = models.EmailField(null=True, blank=True, verbose_name="البريد الإلكتروني لاستعادة كلمة المرور")
    recovery_token = models.CharField(max_length=100, null=True, blank=True, verbose_name="رمز الاستعادة")
    recovery_token_created_at = models.DateTimeField(null=True, blank=True, verbose_name="توقيت إنشاء رمز الاستعادة")

    # Canteen Settings
    canteen_open_time = models.TimeField(default="12:00", null=True, blank=True, verbose_name="وقت فتح المطعم")
    canteen_close_time = models.TimeField(default="13:15", null=True, blank=True, verbose_name="وقت غلق المطعم")
    # Store days as comma-separated integers (0=Mon, 6=Sun).
    canteen_days = models.CharField(max_length=50, default="0,2,3,6", null=True, blank=True, verbose_name="أيام عمل المطعم")

    # AI Tone Settings
    ai_tone = models.CharField(max_length=50, default="professional", verbose_name="نبرة الذكاء الاصطناعي")
    ai_focus = models.CharField(max_length=50, default="academic", verbose_name="تركيز الذكاء الاصطناعي")

    class Meta:
        verbose_name = "إعدادات المؤسسة"
        verbose_name_plural = "إعدادات المؤسسة"

class UserActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="المستخدم")
    action = models.CharField(max_length=50, verbose_name="الإجراء")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="التوقيت")

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "سجل النشاط"
        verbose_name_plural = "سجلات النشاط"

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"

class ArchiveDocument(models.Model):
    reference_number = models.CharField(max_length=50, verbose_name="الرقم")
    service = models.CharField(max_length=100, verbose_name="المصلحة")
    file_type = models.CharField(max_length=100, verbose_name="الملف/السجل")
    document_type = models.CharField(max_length=100, verbose_name="الوثيقة")
    symbol = models.CharField(max_length=50, verbose_name="الرمز", blank=True, null=True)
    student_dob = models.DateField(null=True, blank=True, verbose_name="تاريخ الازدياد (للتلاميذ)")
    entry_date = models.DateField(default=date.today, verbose_name="تاريخ الدخول")
    temp_exit_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الخروج المؤقت")
    elimination_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الحذف أو الإقصاء")
    notes = models.TextField(blank=True, null=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "وثيقة أرشيف"
        verbose_name_plural = "وثائق الأرشيف"

    def __str__(self):
        return f"{self.reference_number} - {self.document_type}"

class EmployeeProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="المستخدم")
    role = models.CharField(max_length=100, verbose_name="الدور")
    failed_login_attempts = models.IntegerField(default=0, verbose_name="محاولات الدخول الفاشلة")
    is_locked = models.BooleanField(default=False, verbose_name="الحساب مقفل")
    current_session_token = models.CharField(max_length=100, null=True, blank=True, verbose_name="رمز الجلسة الحالي")
    device_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="معرف الجهاز")
    permissions = models.JSONField(default=list, blank=True, verbose_name="الصلاحيات")

    # AI Access Control (Director sets this for each user)
    AI_MODE_CHOICES = [
        ('restricted_rag', 'وضع مقيد (RAG) - مساعد إداري'),
        ('educational_free', 'وضع حر (تربوي)'),
        ('full_comprehensive', 'وضع شامل (Gemini Pro Full)'),
    ]
    ai_mode = models.CharField(max_length=30, choices=AI_MODE_CHOICES, default='restricted_rag', verbose_name="صلاحيات الذكاء الاصطناعي")

    totp_secret = models.CharField(max_length=100, null=True, blank=True, verbose_name="مفتاح المصادقة الثنائية")
    totp_enabled = models.BooleanField(default=False, verbose_name="تفعيل المصادقة الثنائية")
    must_change_password = models.BooleanField(default=False, verbose_name="يجب تغيير كلمة المرور")

    def has_perm(self, perm):
        if self.role == 'director' or self.user.is_superuser:
            return True
        return perm in self.permissions

    def __str__(self):
        return f"{self.user.username} - {self.role}"

class PendingUpdate(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="المستخدم")
    model_name = models.CharField(max_length=50, verbose_name="النموذج")
    action = models.CharField(max_length=20, verbose_name="الإجراء")
    data = models.JSONField(verbose_name="البيانات")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="التوقيت")
    status = models.CharField(max_length=20, default='pending', verbose_name="الحالة")

    class Meta:
        verbose_name = "تحديث معلق"
        verbose_name_plural = "التحديثات المعلقة"
        ordering = ['-timestamp']

class SystemMessage(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="المستلم")
    message = models.TextField(verbose_name="الرسالة")
    active = models.BooleanField(default=True, verbose_name="نشطة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الانتهاء")

    class Meta:
        verbose_name = "رسالة النظام"
        verbose_name_plural = "رسائل النظام"

class UserRole(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="اسم الدور")
    permissions = models.JSONField(default=list, verbose_name="الصلاحيات")

    class Meta:
        verbose_name = "دور مخصص"
        verbose_name_plural = "أدوار مخصصة"
        ordering = ['name']

    def __str__(self):
        return self.name

class Employee(models.Model):
    RANK_CHOICES = [
        ('teacher', 'أستاذ'),
        ('worker', 'عامل مهني'),
        ('admin', 'إداري'),
    ]
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_hr', verbose_name="حساب المستخدم")
    employee_code = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name="الرمز الوظيفي")
    last_name = models.CharField(max_length=100, verbose_name="اللقب", default="")
    first_name = models.CharField(max_length=100, verbose_name="الاسم", default="")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="تاريخ الازدياد")
    rank = models.CharField(max_length=20, choices=RANK_CHOICES, default='worker', verbose_name="الرتبة")
    subject = models.CharField(max_length=100, null=True, blank=True, verbose_name="المادة") # Only for teachers
    grade = models.CharField(max_length=50, null=True, blank=True, verbose_name="الدرجة")
    effective_date = models.DateField(null=True, blank=True, verbose_name="تاريخ السريان")
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="رقم الهاتف")
    email = models.EmailField(null=True, blank=True, verbose_name="البريد الإلكتروني")
    social_media_link = models.URLField(null=True, blank=True, verbose_name="رابط التواصل الاجتماعي")
    photo = models.ImageField(upload_to='employee_photos/', null=True, blank=True, verbose_name="الصورة")
    notes = models.TextField(null=True, blank=True, verbose_name="ملاحظات")

    # Legacy Fields (Kept for migration safety, can be deprecated)
    full_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="الاسم الكامل (قديم)")
    role = models.CharField(max_length=100, null=True, blank=True, verbose_name="الوظيفة (قديم)")

    class Meta:
        verbose_name = "موظف"
        verbose_name_plural = "الموارد البشرية"

    def save(self, *args, **kwargs):
        if not self.last_name and self.full_name:
            parts = self.full_name.split(' ', 1)
            self.last_name = parts[0]
            if len(parts) > 1:
                self.first_name = parts[1]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

class TeacherAssignment(models.Model):
    teacher = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='assignments', verbose_name="الأستاذ")
    subject = models.CharField(max_length=100, verbose_name="المادة")
    classes = models.JSONField(default=list, verbose_name="الأقسام المسندة") # List of class names e.g. ["1M1", "2M2"]
    original_file = models.FileField(upload_to='assignments/', null=True, blank=True, verbose_name="ملف الإسناد")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "إسناد تربوي"
        verbose_name_plural = "الإسنادات التربوية"

class Survey(models.Model):
    title = models.CharField(max_length=200, verbose_name="العنوان")
    description = models.TextField(verbose_name="الوصف")
    target_audience = models.CharField(max_length=100, verbose_name="الجمهور المستهدف")
    link = models.URLField(null=True, blank=True, verbose_name="رابط الاستبيان")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "استبيان"
        verbose_name_plural = "الإرشاد والتوجيه"

    def __str__(self):
        return self.title

class AttendanceRecord(models.Model):
    ATTENDANCE_TYPES = [
        ('ABSENT', 'غياب'),
        ('LATE', 'تأخر'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="التلميذ", related_name='attendance_records')
    date = models.DateField(default=date.today, verbose_name="التاريخ")
    time = models.TimeField(null=True, blank=True, verbose_name="وقت الوصول")
    type = models.CharField(max_length=20, choices=ATTENDANCE_TYPES, verbose_name="النوع")
    reason = models.TextField(null=True, blank=True, verbose_name="السبب")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ التسجيل")

    class Meta:
        verbose_name = "سجل الغياب والتأخر"
        verbose_name_plural = "سجلات الغياب والتأخر"
        ordering = ['-date', '-time']

    def __str__(self):
        return f"{self.student} - {self.get_type_display()} - {self.date}"

class Communication(models.Model):
    COMM_TYPES = [
        ('NOTE', 'ملاحظة'),
        ('SUMMONS', 'استدعاء'),
        ('INFO', 'إعلان'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="التلميذ", related_name='communications')
    title = models.CharField(max_length=200, verbose_name="العنوان")
    content = models.TextField(verbose_name="المحتوى")
    date = models.DateField(default=date.today, verbose_name="التاريخ")
    type = models.CharField(max_length=20, choices=COMM_TYPES, default='NOTE', verbose_name="النوع")
    is_read = models.BooleanField(default=False, verbose_name="تمت القراءة")

    class Meta:
        verbose_name = "مراسلة"
        verbose_name_plural = "المراسلات"
        ordering = ['-date']

    def __str__(self):
        return f"{self.student} - {self.title}"

# --- AI & Task System Models ---

class Task(models.Model):
    title = models.CharField(max_length=200, verbose_name="عنوان المهمة")
    description = models.TextField(verbose_name="الوصف التقني")
    assigned_role = models.ForeignKey(UserRole, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="الدور المسند")
    assigned_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="المستخدم المسند")
    manager_instructions = models.TextField(verbose_name="سياق المدير (AI Context)", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الاستحقاق")
    is_completed = models.BooleanField(default=False)

    class Meta:
        verbose_name = "مهمة"
        verbose_name_plural = "المهام"

class TeacherObservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('ai_suggested', 'مقترح AI'),
        ('teacher_approved', 'موافقة الأستاذ'),
        ('admin_review', 'مراجعة المدير'),
        ('delivered', 'تم التسليم'),
        ('rejected', 'مرفوض')
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="التلميذ")
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='observations_created', verbose_name="الأستاذ")
    content = models.TextField(verbose_name="ملاحظة الأستاذ")
    ai_suggestion = models.TextField(verbose_name="مقترح الذكاء الاصطناعي", blank=True, null=True)
    final_content = models.TextField(verbose_name="المحتوى النهائي", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    admin_feedback = models.TextField(verbose_name="رد الإدارة", blank=True, null=True)

    class Meta:
        verbose_name = "ملاحظة تربوية"
        verbose_name_plural = "الملاحظات التربوية"

class SchoolMemory(models.Model):
    CATEGORY_CHOICES = [
        ('rule', 'قانون داخلي'),
        ('curriculum', 'منهاج دراسي'),
        ('solution', 'حل سابق'),
        ('general', 'عام')
    ]
    title = models.CharField(max_length=200, verbose_name="العنوان")
    content = models.TextField(verbose_name="المحتوى")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')

    # New Fields for File Import
    attachment = models.FileField(upload_to='rag_docs/', null=True, blank=True, verbose_name="ملف مرفق")
    url = models.URLField(null=True, blank=True, verbose_name="رابط مرجعي")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ذاكرة المؤسسة"
        verbose_name_plural = "ذاكرة المؤسسة"
