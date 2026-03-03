import os
import django
import pandas as pd
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from students.models import Grade, Student
from students.analytics_utils import analyze_grades_locally

Grade.objects.all().delete()
Student.objects.all().delete()

s = Student.objects.create(
    student_id_number="789",
    last_name="A",
    first_name="B",
    class_name="أولى 1",
    academic_year="أولى",
    date_of_birth=datetime.date(2010, 1, 1),
    enrollment_date=datetime.date(2023, 9, 1)
)

Grade.objects.create(student=s, subject="Math", term="T1", score=10.0)
Grade.objects.create(student=s, subject="Physics", term="T1", score=12.0)
Grade.objects.create(student=s, subject="المعدل العام", term="T1", score=11.0)

res = analyze_grades_locally(Grade.objects.all())
print("Detailed Stats:")
print(res['detailed_subject_stats'])
print("Detailed Stats JSON:")
print(res['detailed_subject_stats_json'])
