with open('students/expert_api_views.py', 'r') as f:
    content = f.read()

content = content.replace("student = Student.objects.filter(student_id_number=s_id).first()",
                          "student = Student.objects.filter(student_id_number=s_id).first()\n                        if not student:\n                            # Try with/without .0 just in case\n                            student = Student.objects.filter(student_id_number=s_id.replace('.0', '') if '.0' in s_id else s_id + '.0').first()")

with open('students/expert_api_views.py', 'w') as f:
    f.write(content)
