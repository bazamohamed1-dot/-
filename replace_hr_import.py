import os

file_path = 'students/ui_views.py'
new_block = """        if action == 'import_file' and request.FILES.get('file'):
            file = request.FILES['file']
            # Save strictly to disk for processing
            temp_path = None
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
                    for chunk in file.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name

                from .import_utils import parse_hr_file
                employees_data = parse_hr_file(temp_path)

                count = 0
                for emp in employees_data:
                    # Parse Rank
                    rank_str = emp.get('rank', 'worker')
                    rank_map = {'أستاذ': 'teacher', 'عامل': 'worker', 'إداري': 'admin', 'مستشار': 'admin', 'مقتصد': 'admin'}
                    rank = 'worker'
                    for key, val in rank_map.items():
                        if key in rank_str:
                            rank = val
                            break

                    # Handle Subject
                    subject = emp.get('subject', '/')
                    if rank != 'teacher':
                        subject = "/"

                    # Dates Parsing
                    def parse_d(val):
                        if not val: return None
                        if isinstance(val, (date, datetime)): return val
                        try: return datetime.strptime(str(val).strip(), '%Y-%m-%d').date()
                        except: pass
                        try: return datetime.strptime(str(val).strip(), '%d/%m/%Y').date()
                        except: pass
                        return None

                    dob = parse_d(emp.get('date_of_birth'))
                    eff_date = parse_d(emp.get('effective_date'))

                    Employee.objects.update_or_create(
                        employee_code=emp.get('employee_code'),
                        defaults={
                            'last_name': emp.get('last_name', ''),
                            'first_name': emp.get('first_name', ''),
                            'full_name': f"{emp.get('last_name', '')} {emp.get('first_name', '')}",
                            'date_of_birth': dob,
                            'rank': rank,
                            'subject': subject,
                            'grade': emp.get('grade', ''),
                            'effective_date': eff_date,
                            'phone': emp.get('phone', ''),
                            'email': emp.get('email', ''),
                            'role': rank
                        }
                    )
                    count += 1

                messages.success(request, f"تم استيراد/تحديث {count} موظف.")
            except Exception as e:
                messages.error(request, f"خطأ في الملف: {e}")
            finally:
                if temp_path and os.path.exists(temp_path):
                    try: os.remove(temp_path)
                    except: pass
            return redirect('hr_home')

"""

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if "if action == 'import_file' and request.FILES.get('file'):" in line:
        start_idx = i
    if "elif action == 'add_manual':" in line and start_idx != -1:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    print(f"Replacing lines {start_idx} to {end_idx}")
    new_lines = lines[:start_idx] + [new_block] + lines[end_idx:]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Success")
else:
    print("Could not find blocks")
