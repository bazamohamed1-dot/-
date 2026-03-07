from django.db import migrations
import re

def populate_shortcuts(apps, schema_editor):
    Student = apps.get_model('students', 'Student')
    ClassShortcut = apps.get_model('students', 'ClassShortcut')

    classes = Student.objects.exclude(class_name__isnull=True).exclude(class_name='').values_list('class_name', flat=True).distinct()

    for class_name in classes:
        class_name = class_name.strip()

        level_num = ""
        if "أول" in class_name or "1" in class_name:
            level_num = "1"
        elif "ثاني" in class_name or "2" in class_name:
            level_num = "2"
        elif "ثال" in class_name or "3" in class_name:
            level_num = "3"
        elif "راب" in class_name or "4" in class_name:
            level_num = "4"

        class_num = ""
        for char in reversed(class_name):
            if char.isdigit():
                class_num = char
                break

        shortcut = class_name
        if level_num and class_num:
            shortcut = f"{level_num}م{class_num}"

        # Add basic try-except or get_or_create logic to handle duplicates securely
        existing = ClassShortcut.objects.filter(full_name=class_name).first()
        if not existing:
            # ensure shortcut is unique as well
            base_shortcut = shortcut
            counter = 1
            while ClassShortcut.objects.filter(shortcut=shortcut).exists():
                shortcut = f"{base_shortcut}_{counter}"
                counter += 1
            ClassShortcut.objects.create(full_name=class_name, shortcut=shortcut)

def reverse_shortcuts(apps, schema_editor):
    ClassShortcut = apps.get_model('students', 'ClassShortcut')
    ClassShortcut.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('students', '0022_classshortcut'),
    ]

    operations = [
        migrations.RunPython(populate_shortcuts, reverse_shortcuts),
    ]
