import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()
from students.models import Employee, TeacherAssignment

e = Employee.objects.filter().first()
if e:
    TeacherAssignment.objects.create(teacher=e, subject="الرياضيات", classes=["أولى 1", "أولى 2", "أولى 3"])
    print("Created mock HR records")
