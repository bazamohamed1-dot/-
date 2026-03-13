import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "School_Management.settings")
django.setup()

from students.models_mapping import SubjectAlias
from django.test import Client
import json

c = Client()
# bypass login
from django.contrib.auth.models import User
user, _ = User.objects.get_or_create(username="testadmin", is_superuser=True)
c.force_login(user)

response = c.post('/canteen/analytics/upload_grades_ajax/', {
    'term': 'الفصل الأول',
    'import_mode': 'local',
    'subject_mappings': json.dumps({"الاعلام الالي 1": "المعلوماتية"}),
    # mock a file path that doesn't exist so it fails gracefully after saving mapping
    'temp_file_path': '/tmp/nonexistent.xlsx'
})

print(response.json())
print("Aliases in DB:", list(SubjectAlias.objects.values_list('alias', 'canonical_name')))
