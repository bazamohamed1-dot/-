import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print("Admin user created")
else:
    print("Admin user already exists")

# Update user password just in case
u = User.objects.get(username='admin')
u.set_password('admin')
u.save()
print("Admin password set to 'admin'")
