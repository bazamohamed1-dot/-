from django.db import models

class ClassAlias(models.Model):
    """
    Maps various class name formats (e.g., "1M1", "1 م 1") to the canonical database class name.
    """
    alias = models.CharField(max_length=50, unique=True, verbose_name="الاسم المستعار (من الملف)")
    canonical_class = models.CharField(max_length=50, verbose_name="الاسم الرسمي (في القاعدة)")

    class Meta:
        verbose_name = "تعيين اسم القسم"
        verbose_name_plural = "تعيينات أسماء الأقسام"

    def __str__(self):
        return f"{self.alias} -> {self.canonical_class}"
