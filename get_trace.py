import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from django.test import Client

client = Client()

response = client.post('/auth/login/', {'username': 'director', 'password': 'password123'})
response = client.get('/canteen/hr/', follow=True)
print("HR Page:", response.status_code)
if response.status_code == 500:
    print(response.content.decode())
