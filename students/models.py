from django.db import models
from datetime import date
from django.contrib.auth.models import User

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
    photo_path = models.TextField(null=True, blank=True, verbose_name="مسار الصورة") # Changed to TextField to support Base64

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
    name = models.CharField(max_length=200, verbose_name="اسم المؤسسة")
    academic_year = models.CharField(max_length=50, verbose_name="السنة الدراسية")
    director_name = models.CharField(max_length=200, verbose_name="اسم المدير")
    logo = models.ImageField(upload_to='school_logo/', null=True, blank=True, verbose_name="شعار المؤسسة")
    loan_limit = models.IntegerField(default=2, verbose_name="الحد الأقصى للإعارات")
    loan_limits_by_level = models.JSONField(default=dict, blank=True, verbose_name="حدود الإعارة حسب المستوى")
    admin_email = models.EmailField(null=True, blank=True, verbose_name="البريد الإلكتروني لاستعادة كلمة المرور")
    recovery_token = models.CharField(max_length=100, null=True, blank=True, verbose_name="رمز الاستعادة")
    recovery_token_created_at = models.DateTimeField(null=True, blank=True, verbose_name="توقيت إنشاء رمز الاستعادة")

    # Canteen Settings
    canteen_open_time = models.TimeField(default="12:00", verbose_name="وقت فتح المطعم")
    canteen_close_time = models.TimeField(default="13:15", verbose_name="وقت غلق المطعم")
    # Store days as comma-separated integers (0=Mon, 6=Sun).
    # Python weekday: Mon=0, Sun=6. JS: Sun=0, Sat=6.
    # We will use Python convention: 0=Monday, 6=Sunday.
    # Default: Sun, Mon, Wed, Thu (0, 2, 3, 6) -> No Tue(1), Fri(4), Sat(5) usually in DZ?
    # User said: "All except Tue, Fri, Sat".
    # Tue=1, Fri=4, Sat=5. So keep 0, 2, 3, 6.
    canteen_days = models.CharField(max_length=50, default="0,2,3,6", verbose_name="أيام عمل المطعم")

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
    INTERFACE_CHOICES = [
        ('all', 'كامل الصلاحيات'),
        ('canteen', 'المطعم المدرسي'),
        ('library', 'المكتبة'),
        ('students', 'تسيير التلاميذ'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="المستخدم")
    # Removed strict choices to allow custom role names
    role = models.CharField(max_length=100, verbose_name="الدور")
    failed_login_attempts = models.IntegerField(default=0, verbose_name="محاولات الدخول الفاشلة")
    is_locked = models.BooleanField(default=False, verbose_name="الحساب مقفل")
    current_session_token = models.CharField(max_length=100, null=True, blank=True, verbose_name="رمز الجلسة الحالي")
    device_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="معرف الجهاز")
    permissions = models.JSONField(default=list, blank=True, verbose_name="الصلاحيات")

    # Cloud Control
    is_active_cloud = models.BooleanField(default=True, verbose_name="تفعيل الدخول السحابي")
    assigned_interface = models.CharField(max_length=50, choices=INTERFACE_CHOICES, default='all', verbose_name="الواجهة المخصصة")

    # 2FA Fields
    totp_secret = models.CharField(max_length=100, null=True, blank=True, verbose_name="مفتاح المصادقة الثنائية")
    totp_enabled = models.BooleanField(default=False, verbose_name="تفعيل المصادقة الثنائية")
    must_change_password = models.BooleanField(default=False, verbose_name="يجب تغيير كلمة المرور")

    def has_perm(self, perm):
        if self.role == 'director' or self.user.is_superuser:
            return True
        return perm in self.permissions

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

class PendingUpdate(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="المستخدم")
    model_name = models.CharField(max_length=50, verbose_name="النموذج")
    action = models.CharField(max_length=20, verbose_name="الإجراء") # create, update, delete
    data = models.JSONField(verbose_name="البيانات")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="التوقيت")
    status = models.CharField(max_length=20, default='pending', verbose_name="الحالة") # pending, approved, rejected

    class Meta:
        verbose_name = "تحديث معلق"
        verbose_name_plural = "التحديثات المعلقة"
        ordering = ['-timestamp']

class SystemMessage(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="المستلم") # Null = All users
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
    full_name = models.CharField(max_length=200, verbose_name="الاسم الكامل")
    role = models.CharField(max_length=100, verbose_name="الوظيفة") # Teacher, Admin, Worker
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="رقم الهاتف")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="تاريخ الميلاد")
    notes = models.TextField(null=True, blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "موظف"
        verbose_name_plural = "الموارد البشرية"

    def __str__(self):
        return self.full_name

class Survey(models.Model):
    title = models.CharField(max_length=200, verbose_name="العنوان")
    description = models.TextField(verbose_name="الوصف")
    target_audience = models.CharField(max_length=100, verbose_name="الجمهور المستهدف") # Students, Parents, Staff
    link = models.URLField(null=True, blank=True, verbose_name="رابط الاستبيان") # External (Google Forms) or internal
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
    time = models.TimeField(null=True, blank=True, verbose_name="وقت الوصول") # For lateness
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
