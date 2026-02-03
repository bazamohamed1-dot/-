from django.db import models

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
    enrollment_number = models.CharField(max_length=50, unique=True, verbose_name="رقم القيد")
    enrollment_date = models.DateField(verbose_name="تاريخ التسجيل")
    exit_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الخروج")
    guardian_name = models.CharField(max_length=200, verbose_name="اسم الولي")
    mother_name = models.CharField(max_length=200, verbose_name="لقب واسم الأم")
    address = models.TextField(verbose_name="عنوان السكن")
    guardian_phone = models.CharField(max_length=20, verbose_name="رقم هاتف الولي")
    photo_path = models.CharField(max_length=255, null=True, blank=True, verbose_name="مسار الصورة")

    class Meta:
        verbose_name = "تلميذ"
        verbose_name_plural = "التلاميذ"

    def __str__(self):
        return f"{self.last_name} {self.first_name}"
