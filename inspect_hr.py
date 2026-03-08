import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()
from django.template import Template, Context
from students.models import Employee

t = Template("{% load student_tags %}<button onclick='openAddModal(\"{{ emp.id }}\", JSON.parse(\"{{ emp|safe_json|escapejs }}\"))'></button>")

emp = Employee.objects.create(
    first_name="Test",
    last_name="Test",
    notes="Some notes with 'single' and \"double\" quotes and \n newlines."
)

c = Context({'emp': emp})
try:
    print(t.render(c))
except Exception as e:
    print("Error:", e)
