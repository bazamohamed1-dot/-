import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "School_Management.settings")
django.setup()

from django.test.client import Client
from django.contrib.auth.models import User
import traceback

client = Client()
user, _ = User.objects.get_or_create(username='director', is_superuser=True)
client.force_login(user)

# Mock session data
session = client.session
session['ai_extracted_data'] = [
    {"name": "محمد بن علي", "subject": "رياضيات", "classes": ["1م1"]}
]
session.save()

try:
    response = client.get('/canteen/hr/assignment_match/?step=3')
    print("Status:", response.status_code)
    if response.status_code == 500:
        print("Response content:")
        print(response.content.decode('utf-8')[:2000])
except Exception as e:
    traceback.print_exc()
