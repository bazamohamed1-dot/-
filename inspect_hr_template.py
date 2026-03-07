from django.template.loader import render_to_string
import django
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from django.template import Context, Template
from students.models import Employee, EmployeeProfile

try:
    with open('students/templates/students/hr.html', 'r', encoding='utf-8') as f:
        template = Template(f.read())

    print("Template parsed successfully!")
except Exception as e:
    print(f"Error parsing template: {e}")
