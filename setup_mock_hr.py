import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()
from students.models import Employee
Employee.objects.create(
    employee_code="T001",
    first_name="أحمد",
    last_name="محمود",
    rank="أستاذ",
    assignments=[{"subject": "الرياضيات", "classes": ["أولى 1", "ثانية 2", "أولى 2", "رابعة 1"]}],
    subject="الرياضيات"
)
Employee.objects.create(
    employee_code="T002",
    first_name="سعاد",
    last_name="علي",
    rank="أستاذ",
    assignments=[{"subject": "ع الطبيعة والحياة", "classes": ["1م1", "1م2", "2م1"]}],
    subject="ع الطبيعة والحياة"
)
print("Created mock HR records")
