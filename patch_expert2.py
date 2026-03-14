with open('students/expert_api_views.py', 'r') as f:
    content = f.read()

content = content.replace("s_id = str(row[id_col]).strip() if id_col != -1 and len(row) > id_col and row[id_col] else None",
                          "s_id = str(row[id_col]).strip() if id_col != -1 and len(row) > id_col and row[id_col] else None\n                    if s_id and s_id.endswith('.0'):\n                        s_id = s_id[:-2]")

with open('students/expert_api_views.py', 'w') as f:
    f.write(content)
