from django.db import models

class ClassAlias(models.Model):
    """
    Maps various class name formats (e.g., "1M1", "1 م 1") to the canonical database level and class number.
    """
    alias = models.CharField(max_length=50, unique=True, verbose_name="الاسم المستعار (من الملف)")
    canonical_level = models.CharField(max_length=50, verbose_name="المستوى الموافق (في القاعدة)", default="")
    canonical_class = models.CharField(max_length=50, verbose_name="القسم الموافق (في القاعدة)")

    class Meta:
        verbose_name = "تعيين اسم القسم"
        verbose_name_plural = "تعيينات أسماء الأقسام"

    def __str__(self):
        return f"{self.alias} -> {self.canonical_level} {self.canonical_class}"

class TeacherAlias(models.Model):
    """
    Maps a teacher's name found in an imported file to the actual Employee (teacher) in the database.
    """
    alias_name = models.CharField(max_length=150, unique=True, verbose_name="الاسم المستعار (من الملف)")
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='aliases', verbose_name="الأستاذ الموافق (في القاعدة)")

    class Meta:
        verbose_name = "تعيين اسم الأستاذ"
        verbose_name_plural = "تعيينات أسماء الأساتذة"

    def __str__(self):
        return f"{self.alias_name} -> {self.employee.full_name}"
