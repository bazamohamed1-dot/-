with open("students/templates/students/analytics.html", "r") as f:
    content = f.read()

s1 = """                <option value="{{ t.id }}" data-assignments='{{ t.analytics_assignments|safe_json|escapejs }}' data-name="{{ t.last_name }} {{ t.first_name }}">{{ t.last_name }} {{ t.first_name }}</option>"""

r1 = """                <option value="{{ t.id }}" data-assignments='{{ t.analytics_assignments|safe_json|escapejs }}' data-hr-assignments='{{ t|get_assignments_data|escapejs }}' data-name="{{ t.last_name }} {{ t.first_name }}">{{ t.last_name }} {{ t.first_name }}</option>"""

content = content.replace(s1, r1)

with open("students/templates/students/analytics.html", "w") as f:
    f.write(content)
