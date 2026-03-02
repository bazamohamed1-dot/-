import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from django.test.client import RequestFactory
from django.contrib.auth.models import AnonymousUser, User
import students.ui_views as ui

rf = RequestFactory()

# Mock user with profile
try:
    user = User.objects.get(username="test_admin")
except User.DoesNotExist:
    user = User.objects.create_user("test_admin", "admin@test.com", "pass")
    from students.models import EmployeeProfile, Employee
    emp = Employee.objects.create(last_name="admin")
    EmployeeProfile.objects.create(user=user, role="director")
    emp.user = user
    emp.save()

from students.models import Grade, Student
# Ensure DB is COMPLETELY empty for grades and students
Grade.objects.all().delete()
Student.objects.all().delete()

def test_view(view_func, url):
    request = rf.get(url)
    request.user = user
    # Mock full session object
    from importlib import import_module
    from django.conf import settings
    engine = import_module(settings.SESSION_ENGINE)
    session = engine.SessionStore()
    session.save()
    request.session = session

    try:
        response = view_func(request)
        print(f"{url} -> {response.status_code}")
        if response.status_code == 500:
            print(response.content.decode('utf-8'))
    except Exception as e:
        print(f"Error on {url}:")
        import traceback
        traceback.print_exc()

test_view(ui.analytics_dashboard, '/canteen/analytics/')
