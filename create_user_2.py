import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "School_Management.settings")
django.setup()
from django.contrib.auth.models import User
from students.models import EmployeeProfile

try:
    u, created = User.objects.get_or_create(username='librarian_user')
    u.set_password('libpass123')
    u.save()
    EmployeeProfile.objects.update_or_create(user=u, defaults={'role': 'librarian'})
    print("User librarian_user created successfully")
except Exception as e:
    print(f"Error creating user: {e}")
