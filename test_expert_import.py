import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "School_Management.settings")
django.setup()

from students.models import Student
try:
    student4 = Student.objects.create(student_id_number="123456", first_name="test4", last_name="test4", date_of_birth='2000-01-01', enrollment_date='2000-01-01', academic_year='أولى متوسط', class_name='أولى 1', class_code='1م1')
    print("created 4")
except Exception as e:
    print("error", e)
