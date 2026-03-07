import os
import django
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "School_Management.settings")
django.setup()

from django.test.client import Client
from django.contrib.auth.models import User
from students.models import Employee, TeacherAssignment

client = Client()
user, _ = User.objects.get_or_create(username='director', is_superuser=True)
client.force_login(user)

# 1. Setup edge case data
emp = Employee.objects.filter(rank='teacher').first()
if not emp:
    emp = Employee.objects.create(rank='teacher', last_name='Test', first_name='Test')
TeacherAssignment.objects.create(teacher=emp, subject='Math')
TeacherAssignment.objects.create(teacher=emp, subject='Math')

# 2. Mock session
session = client.session
session['ai_extracted_data'] = [
    {"name": "Test Test", "subject": "Math", "classes": ["1M1"]},
    {"name": "Missing Classes", "subject": "Sci"} # No classes key
]
session.save()

# 3. Test GET
print("Testing GET /canteen/hr/assignment_match/?step=3")
try:
    response = client.get('/canteen/hr/assignment_match/?step=3')
    print("GET Status:", response.status_code)
except Exception as e:
    print("GET EXCEPTION:")
    traceback.print_exc()

# 4. Test POST
print("\nTesting POST /canteen/hr/assignment_match/?step=3")
try:
    response = client.post('/canteen/hr/assignment_match/?step=3', {
        'match_0': emp.id,
        'name_0': 'Test Test',
        'subject_0': 'Math',
        'classes_0': '["1M1"]',
        'match_1': 'ignore'
    })
    print("POST Status:", response.status_code)
except Exception as e:
    print("POST EXCEPTION:")
    traceback.print_exc()
