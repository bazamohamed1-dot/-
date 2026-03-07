from django.template.loader import render_to_string
import django
import os
import sys
from django.test import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from students.models import User

client = Client()
try:
    user = User.objects.get(username='director')
except:
    user = User.objects.create_superuser('director', 'director@test.com', 'password')

client.force_login(user)
try:
    response = client.get('/canteen/hr/')
    print(response.status_code)
    if response.status_code != 200:
        print("Error content:")
        # Look for the error summary in the HTML
        import bs4
        soup = bs4.BeautifulSoup(response.content, 'html.parser')
        err = soup.find('div', id='summary')
        if err:
            print(err.text.strip())
        else:
            print(response.content.decode('utf-8')[:2000])
except Exception as e:
    import traceback
    traceback.print_exc()
