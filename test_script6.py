import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth.models import User
from students.models import Employee, TeacherAssignment, Student
from students.models_mapping import ClassShortcut

def run_tests():
    # clean db
    ClassShortcut.objects.all().delete()
    TeacherAssignment.objects.all().delete()
    Student.objects.all().delete()

    # create some data in student table that would have caused the '1', '2' bug
    Student.objects.create(student_id_number="1", last_name="A", first_name="A", gender="M", date_of_birth="2000-01-01", place_of_birth="X", academic_year="4 متوسط", class_name="1")
    Student.objects.create(student_id_number="2", last_name="B", first_name="B", gender="M", date_of_birth="2000-01-01", place_of_birth="X", academic_year="4 متوسط", class_name="2")
    Student.objects.create(student_id_number="3", last_name="C", first_name="C", gender="M", date_of_birth="2000-01-01", place_of_birth="X", academic_year="3 متوسط", class_name="1")

    User.objects.filter(username='test_admin').delete()
    user = User.objects.create_superuser('test_admin', 'admin@example.com', 'adminpass')
    c = Client()
    c.force_login(user)

    res = c.get('/canteen/hr/')
    print("Status code:", res.status_code)

    html = res.content.decode('utf-8')
    # Use regular expressions or simple parsing

    import re
    if re.search(r'4م1', html) and re.search(r'4م2', html) and re.search(r'3م1', html):
        print("Classes properly formatted in UI")
    else:
        print("Classes NOT properly formatted")

    if re.search(r'value="1"', html) and not re.search(r'1م1', html):
        print("Found old raw numbers '1', '2' instead of formatted strings!")

run_tests()
