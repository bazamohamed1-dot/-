with open('students/expert_api_views.py', 'r') as f:
    content = f.read()

content = content.replace("fake_id = s_id if s_id else str(random.randint(10000000, 99999999))",
                          "fake_id = s_id if s_id and not s_id.endswith('.0') else (s_id[:-2] if s_id and s_id.endswith('.0') else str(random.randint(10000000, 99999999)))")

with open('students/expert_api_views.py', 'w') as f:
    f.write(content)
