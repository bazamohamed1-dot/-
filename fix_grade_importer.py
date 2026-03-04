import re

file_path = './students/grade_importer.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Improve Local Parsing Logic using fuzzy matching and more robust regex
improved_logic = """
    # Map Subject Name -> Column Index
    subject_indices = {}
    name_idx = -1
    repeater_idx = -1

    import difflib

    known_subjects = [
        'اللغة العربية', 'الرياضيات', 'العلوم الفيزيائية', 'الفيزياء', 'علوم الطبيعة والحياة', 'العلوم الطبيعية',
        'التربية الإسلامية', 'التربية المدنية', 'التاريخ والجغرافيا', 'التاريخ', 'الجغرافيا',
        'اللغة الفرنسية', 'الفرنسية', 'اللغة الإنجليزية', 'الإنجليزية', 'اللغة الأمازيغية', 'الأمازيغية',
        'التربية الفنية', 'الفنية', 'الرسم', 'التربية الموسيقية', 'الموسيقى', 'التربية البدنية', 'الرياضة',
        'الإعلام الآلي', 'المعلوماتية'
    ]

    for idx, header in enumerate(headers):
        # Clean header text aggressively
        clean_header = header.replace('\\n', ' ').replace('\\r', '').strip()
        # Remove common terms like "ف 1"
        clean_header = re.sub(r'(ف|الفصل)\\s*\\d+', '', clean_header).strip()

        if 'اللقب' in clean_header or 'الاسم' in clean_header or 'الاسم واللقب' in clean_header or 'اللقب والاسم' in clean_header:
            if name_idx == -1: # Only set once to avoid matching wrong columns later
                name_idx = idx
        elif 'الإعادة' in clean_header or 'الاعادة' in clean_header:
            repeater_idx = idx
        elif 'المعدل العام' in clean_header or 'معدل الفصل' in clean_header:
            subject_indices['المعدل العام'] = idx
        else:
            # Fuzzy match against known subjects
            matches = difflib.get_close_matches(clean_header, known_subjects, n=1, cutoff=0.7)
            if matches:
                subject_indices[matches[0]] = idx
            elif clean_header and len(clean_header) > 3 and clean_header not in ['الرقم', 'رقم', 'الملاحظة', 'التقدير', 'الغياب', 'المواظبة', 'اللقبوالاسم', 'الاسمواللقب']:
                # If it's a completely new subject name not in our known list
                subject_indices[clean_header] = idx

    # Fallback if no subjects found (try to read by index 5 to 18)
    if len(subject_indices) == 0:
"""

# We must escape backslashes in the replacement string because `re.sub` parses `\s`
improved_logic = improved_logic.replace('\\', '\\\\')

content = re.sub(r"# Map Subject Name -> Column Index.*?# If it's Term 1 and subjects don't have suffix.*?if len\(subject_indices\) == 0:", improved_logic, content, flags=re.DOTALL)


# 2. Add AI logic function
ai_func = """
def process_grades_file_ai(file_path, term):
    \"\"\"
    Sends the extracted text from the Excel/PDF file to the LLM (AIService)
    to intelligently extract grades and student data into JSON format.
    \"\"\"
    import os
    import json
    from .import_utils import extract_rows_from_file
    from .ai_utils import AIService

    # 1. Extract raw text from file
    raw_text = ""
    try:
        with open(file_path, 'rb') as f:
            rows = list(extract_rows_from_file(f, override_filename=file_path))
            for row in rows[:100]: # Limit to avoid massive token payload
                raw_text += " | ".join([str(c) for c in row if c]) + "\\n"
    except Exception as e:
        return 0, f"خطأ في قراءة الملف محلياً قبل إرساله للذكاء الاصطناعي: {str(e)}"

    if not raw_text.strip():
        return 0, "الملف يبدو فارغاً."

    # 2. Construct AI Prompt
    system_prompt = \"\"\"
أنت مساعد ذكي لاستخراج بيانات كشوف النقاط من جداول غير منتظمة.
البيانات المستلمة هي صفوف نصية. مهمتك استخراج:
1. المستوى والقسم (مثال: '1 متوسط 2' أو '1م2').
2. قائمة بالتلاميذ تحتوي على:
   - student_name: الاسم الكامل.
   - is_repeater: هل هو معيد؟ (true/false) بناء على عمود الإعادة أو الملاحظة.
   - grades: قاموس (Dictionary) يحتوي على اسم المادة وعلامتها (رقم عشري من 0 إلى 20).
     تأكد من توحيد أسماء المواد (مثال: 'اللغة العربية', 'الرياضيات', 'المعدل العام').

تجاهل الصفوف الفارغة أو الترويسات.
يجب إرجاع النتيجة حصرياً بصيغة JSON بالتنسيق التالي بدون أي نص إضافي أو شرح:
{
  "level": "1 متوسط",
  "class_number": "2",
  "students": [
    {
      "student_name": "محمد أمين",
      "is_repeater": false,
      "grades": {"اللغة العربية": 15.5, "الرياضيات": 12.0, "المعدل العام": 14.2}
    }
  ]
}
\"\"\"

    # 3. Call AI Service
    ai_service = AIService()
    ai_response = ai_service.generate_response(raw_text, system_prompt=system_prompt)

    if not ai_response:
        return 0, "لم يتمكن الذكاء الاصطناعي من تحليل الملف، الخادم لا يستجيب أو البيانات معقدة جداً."

    # 4. Parse JSON Response
    try:
        # Strip markdown formatting if any
        json_str = ai_response.replace('```json', '').replace('```', '').strip()
        data = json.loads(json_str)
    except Exception as e:
        return 0, "لم يرجع الذكاء الاصطناعي بيانات بتنسيق JSON صحيح. حاول مرة أخرى."

    # 5. Process the JSON data and insert into DB
    lvl = data.get('level', '')
    cls = str(data.get('class_number', ''))
    students_data = data.get('students', [])

    if not lvl or not cls or not students_data:
        return 0, "تعذر على الذكاء الاصطناعي تحديد القسم أو التلاميذ من الملف."

    students_in_class = Student.objects.filter(academic_year=lvl, class_name=cls)
    if not students_in_class.exists():
        return 0, f"القسم {lvl} {cls} غير موجود في قاعدة البيانات أو ليس به تلاميذ."

    grades_created = 0

    for s_data in students_data:
        student_name = s_data.get('student_name', '').strip()
        is_repeater = s_data.get('is_repeater', False)
        grades = s_data.get('grades', {})

        if not student_name: continue

        # Find student by fuzzy matching
        student = None
        for s in students_in_class:
            if s.full_name == student_name or f"{s.last_name} {s.first_name}" == student_name:
                student = s
                break

        # Reverse name logic
        if not student:
            parts = student_name.split()
            if len(parts) >= 2:
                rev_name = f"{parts[1]} {parts[0]}"
                for s in students_in_class:
                    if rev_name in s.full_name or s.full_name in student_name:
                        student = s
                        break

        if student:
            if student.is_repeater != is_repeater:
                student.is_repeater = is_repeater
                student.save(update_fields=['is_repeater'])

            for subject, score in grades.items():
                try:
                    score_val = float(score)
                    Grade.objects.update_or_create(
                        student=student,
                        subject=subject,
                        term=term,
                        defaults={'score': score_val}
                    )
                    grades_created += 1
                except (ValueError, TypeError):
                    pass

    return grades_created, f"تم استيراد {grades_created} علامة بنجاح للقسم {lvl} {cls} باستخدام الذكاء الاصطناعي."
"""

content += "\n" + ai_func

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated grade_importer.py")
