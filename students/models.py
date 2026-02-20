from django.db import models
from django.contrib.auth.models import User

# ... existing models ...

class UserRole(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="اسم الدور")
    permissions = models.JSONField(default=list, verbose_name="الصلاحيات")

    class Meta:
        verbose_name = "دور مخصص"
        verbose_name_plural = "أدوار مخصصة"
        ordering = ['name']  # Added ordering to fix pagination warning

    def __str__(self):
        return self.name

# ... rest of models ...
