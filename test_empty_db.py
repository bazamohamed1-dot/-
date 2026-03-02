import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from students.models import Grade
from students.analytics_utils import analyze_grades_locally

# Test with no data
Grade.objects.all().delete()

try:
    res = analyze_grades_locally(Grade.objects.all())
    print("Empty DB Result:", res)
except Exception as e:
    import traceback
    traceback.print_exc()
