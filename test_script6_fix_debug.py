import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from students.models import Student
from students.models_mapping import ClassShortcut
from datetime import date

db_combinations = list(Student.objects.exclude(academic_year__isnull=True).exclude(academic_year='')
                                .exclude(class_name__isnull=True).exclude(class_name='')
                                .values_list('academic_year', 'class_name').distinct())

db_classes = []
for level, cl_name in db_combinations:
    full = f"{level} {cl_name}".strip()
    print("Full:", full)
    shortcut_obj = ClassShortcut.objects.filter(full_name=full).first()
    if shortcut_obj:
        db_classes.append(shortcut_obj.shortcut)
    else:
        first_char = level[0] if level else ""
        if first_char.isdigit():
             db_classes.append(f"{first_char}م{cl_name}")
        else:
             db_classes.append(full)
print(db_classes)
