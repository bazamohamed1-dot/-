import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "School_Management.settings")
django.setup()

from students.ui_views import assignment_matching_view
from students.models import Employee
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.models import User

# Add bad teacher
Employee.objects.create(rank='teacher', last_name=None, first_name=None)

rf = RequestFactory()
request = rf.get('/canteen/hr/assignment_match/?step=3')
middleware = SessionMiddleware(lambda r: None)
middleware.process_request(request)
request.session.save()

# Add dummy user
user, _ = User.objects.get_or_create(username='test_admin')
request.user = user

# Add dummy AI extracted data
request.session['ai_extracted_data'] = [
    {"name": "محمد بن علي", "subject": "رياضيات", "classes": ["1م1"]}
]

try:
    response = assignment_matching_view(request)
    print("Success:", response.status_code)
except Exception as e:
    import traceback
    traceback.print_exc()
