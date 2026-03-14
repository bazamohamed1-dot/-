import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()
from students.models import Employee, TeacherAssignment

# Get existing employees
for e in Employee.objects.all():
    print(f"Teacher {e.full_name}")
    TeacherAssignment.objects.create(teacher=e, subject="الرياضيات", assigned_class="أولى 1")
    TeacherAssignment.objects.create(teacher=e, subject="الرياضيات", assigned_class="أولى 2")
    break

print("Created mock HR records")
