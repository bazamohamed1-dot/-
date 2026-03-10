import re

with open('students/templates/base.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace any occurrence of /canteen/api/system_messages/ with /api/system_messages/ just to be sure it matches standard API paths, but wait: the rest of the application uses /canteen/api/. Let's check URLs again.
