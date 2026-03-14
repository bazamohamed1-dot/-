import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()
from students.models import Employee, TeacherAssignment
e1 = Employee.objects.create(
    employee_code="T001",
    first_name="أحمد",
    last_name="محمود",
    rank="أستاذ",
    subject="الرياضيات"
)
TeacherAssignment.objects.create(teacher=e1, subject="الرياضيات", assigned_class="أولى 1")
TeacherAssignment.objects.create(teacher=e1, subject="الرياضيات", assigned_class="أولى 2")
TeacherAssignment.objects.create(teacher=e1, subject="الرياضيات", assigned_class="ثالثة 3")

e2 = Employee.objects.create(
    employee_code="T002",
    first_name="سعاد",
    last_name="علي",
    rank="أستاذ",
    subject="ع الطبيعة والحياة"
)
TeacherAssignment.objects.create(teacher=e2, subject="ع الطبيعة والحياة", assigned_class="1م1")

print("Created mock HR records")
