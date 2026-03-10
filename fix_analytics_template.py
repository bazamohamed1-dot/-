with open('students/templates/students/analytics.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "{% endif %} fs-6\">" in line:
        skip = True
        # remove the previous {% endif %} too
        new_lines[-1] = new_lines[-1].replace("{% endif %}", "")
        new_lines.append("{% endif %}\n")
        continue

    if skip:
        if "{% endif %}" in line:
            skip = False
        continue

    new_lines.append(line)

with open('students/templates/students/analytics.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
