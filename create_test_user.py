import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "School_Management.settings")
django.setup()
from django.contrib.auth.models import User
from students.models import EmployeeProfile

u, created = User.objects.get_or_create(username='test_user')
u.set_password('testpass')
u.save()
EmployeeProfile.objects.update_or_create(user=u, defaults={'role': 'librarian'})
print("User created")
