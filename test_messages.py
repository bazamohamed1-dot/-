import os
import django
import sys

# Ensure the app is in the sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from students.models import SystemMessage
from django.contrib.auth.models import User

print("Existing Messages:", SystemMessage.objects.all().count())
for msg in SystemMessage.objects.all():
    print(f"[{msg.id}] to {msg.recipient}: {msg.message} (Active: {msg.active})")
