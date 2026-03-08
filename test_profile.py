import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()
from django.contrib.auth.models import User
from students.models import EmployeeProfile

user = User.objects.create(username='test_user_no_profile_2')
# profile does NOT exist
try:
    print(hasattr(user, 'profile'))
except Exception as e:
    print("Error:", e)
