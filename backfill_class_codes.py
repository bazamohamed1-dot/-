import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from students.models import Student

students = Student.objects.all()
count = 0
for s in students:
    if not s.class_code:
        s.class_code = s.generate_class_code()
        s.save(update_fields=['class_code'])
        count += 1

print(f"Updated {count} students with class_code.")
