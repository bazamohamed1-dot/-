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
    admin_email = models.EmailField(null=True, blank=True, verbose_name="البريد الإلكتروني لاستعادة كلمة المرور")

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
    ROLE_CHOICES = [
        ('director', 'مدير'),
        ('librarian', 'مكتبي'),
        ('storekeeper', 'مخزني'), # Canteen
        ('archivist', 'أرشيفي'),
        ('secretariat', 'أمانة'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="المستخدم")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="الدور")
    failed_login_attempts = models.IntegerField(default=0, verbose_name="محاولات الدخول الفاشلة")
    is_locked = models.BooleanField(default=False, verbose_name="الحساب مقفل")
    current_session_token = models.CharField(max_length=100, null=True, blank=True, verbose_name="رمز الجلسة الحالي")
    device_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="معرف الجهاز")
    permissions = models.JSONField(default=list, blank=True, verbose_name="الصلاحيات")

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
    message = models.TextField(verbose_name="الرسالة")
    active = models.BooleanField(default=True, verbose_name="نشطة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الانتهاء")

    class Meta:
        verbose_name = "رسالة النظام"
        verbose_name_plural = "رسائل النظام"
