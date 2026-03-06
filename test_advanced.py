import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from students.ui_views import advanced_analytics_view
from django.test import RequestFactory
from django.contrib.auth.models import User

rf = RequestFactory()
request = rf.get('/canteen/analytics/advanced/')
request.user = User.objects.get(username='admin')

try:
    response = advanced_analytics_view(request)
    print("Response status code:", response.status_code)
except Exception as e:
    import traceback
    traceback.print_exc()
