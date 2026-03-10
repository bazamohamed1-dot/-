
import re
from .models import Grade, Student, ClassAlias

def process_grades_file(file_path, term):
    from .import_utils import extract_rows_from_file
    from .mapping_views import resolve_class_alias

    with open(file_path, 'rb') as f:
        rows = list(extract_rows_from_file(f, override_filename=file_path))

    if not rows or len(rows) < 7:
        return 0, 'الملف فارغ أو لا يحتوي على بنية علامات صحيحة'

    import os
    # Robust Class Extraction: Scan the first 10 rows for patterns like 'أولى متوسط 1'
    lvl, cls = None, None
    class_name_raw = ""

    # Regex to capture Level (أولى/ثانية/ثالثة/رابعة) and Class Number (\d+)
    # It handles cases like "قسم: أولى متوسط 1", "أولى 1", "رابعة متوسط 01" etc.
    pattern = re.compile(r'(أولى|ثانية|ثالثة|رابعة)(?:\s+متوسط)?\s*[-_]?\s*(\d+)')

    for r_idx in range(min(10, len(rows))):
        for cell in rows[r_idx]:
            cell_str = str(cell).strip()
            match = pattern.search(cell_str)
            if match:
                class_name_raw = cell_str
                lvl = match.group(1) # e.g., 'أولى'
                cls = match.group(2) # e.g., '01'
                # Strip leading zeros so '01' becomes '1'
                cls = str(int(cls))
                break
        if lvl and cls:
            break

    # If not found in the file content, try to extract from the filename
    if not lvl or not cls:
        filename = os.path.basename(file_path)
        match = pattern.search(filename)
        if match:
            class_name_raw = filename
            lvl = match.group(1)
            cls = str(int(match.group(2)))

    # If regex failed, maybe it's in a known Alias format (e.g., '1م1') in the first cell of row 4 or 5
    if not lvl or not cls:
        possible_strings = []
        if len(rows) > 3 and len(rows[3]) > 0: possible_strings.append(str(rows[3][0]))
        if len(rows) > 4 and len(rows[4]) > 0: possible_strings.append(str(rows[4][0]))

        for p_str in possible_strings:
            class_name_raw = p_str
            # Try to resolve using ClassAlias database
            r_lvl, r_cls = resolve_class_alias(p_str.strip())
            if r_lvl and r_cls:
                lvl, cls = r_lvl, r_cls
                break

    if not lvl or not cls:
        return 0, f'تعذر تحديد القسم (المستوى والرقم) من الملف. تأكد من وجود اسم القسم مثل "أولى متوسط 1". النص الذي تم قراءته: {class_name_raw}'

    # Ensure class exists in our DB
    students_in_class = Student.objects.filter(academic_year=lvl, class_name=cls)
    if not students_in_class.exists():
        return 0, f'القسم {lvl} {cls} غير موجود أو لا يحتوي على تلاميذ.'

    # Find the right suffix for the term
    if term == 'الفصل الأول':
        suffix = ' ف 1'
        avg_col_name = 'معدل الفصل 1'
    elif term == 'الفصل الثاني':
        suffix = ' ف 2'
        avg_col_name = 'معدل الفصل 2'
    else:
        suffix = ' ف 3'
        avg_col_name = 'معدل الفصل 3'

    headers = [str(c).strip() for c in rows[5]] # Row 6 is index 5


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

    # Determine the target term suffix explicitly to filter correctly if multiple terms exist in the file
    target_suffix_num = "1" if term == "الفصل الأول" else ("2" if term == "الفصل الثاني" else "3")

    for idx, header in enumerate(headers):
        # Keep original to check for term suffixes
        original_header = header.replace('\n', ' ').replace('\r', '').strip()

        # Clean header text for subject matching
        clean_header = re.sub(r'(ف|الفصل)\s*\d+', '', original_header).strip()

        if 'اللقب' in clean_header or 'الاسم' in clean_header or 'الاسم واللقب' in clean_header or 'اللقب والاسم' in clean_header:
            if name_idx == -1: # Only set once to avoid matching wrong columns later
                name_idx = idx
        elif 'الإعادة' in clean_header or 'الاعادة' in clean_header:
            repeater_idx = idx
        elif 'المعدل العام' in clean_header or 'معدل الفصل' in clean_header:
            # If multiple general averages exist, only take the one matching the current term
            # Or if it doesn't have a term marker, just take the first one
            match_term = re.search(r'(ف|الفصل)\s*(\d+)', original_header)
            if match_term:
                if match_term.group(2) == target_suffix_num:
                    subject_indices['المعدل العام'] = idx
            else:
                # If no term specified in header, just grab it
                subject_indices['المعدل العام'] = idx
        else:
            # If the column has a term suffix (e.g. "الرياضيات ف2"), skip it IF it's not the term we are currently importing!
            match_term = re.search(r'(ف|الفصل)\s*(\d+)', original_header)
            if match_term and match_term.group(2) != target_suffix_num:
                continue # Skip columns belonging to other terms

            # Fuzzy match against known subjects
            matches = difflib.get_close_matches(clean_header, known_subjects, n=1, cutoff=0.7)
            if matches:
                subject_indices[matches[0]] = idx
            elif clean_header and len(clean_header) > 3 and clean_header not in ['الرقم', 'رقم', 'الملاحظة', 'التقدير', 'الغياب', 'المواظبة', 'اللقبوالاسم', 'الاسمواللقب']:
                # If it's a completely new subject name not in our known list
                subject_indices[clean_header] = idx

    # Fallback if no subjects found (try to read by index 5 to 18)
    if len(subject_indices) == 0:

        for idx in range(5, min(19, len(headers))):
            header = headers[idx]
            clean_header = header.replace('\n', ' ').strip()
            # Try to remove any suffix if present
            clean_header = re.sub(r'ف\s*\d+', '', clean_header).strip()

            # Map average column correctly
            if 'المعدل العام' in clean_header or 'معدل الفصل' in clean_header:
                subject_indices['المعدل العام'] = idx
            elif clean_header and clean_header != '':
                subject_indices[clean_header] = idx

    # Fallback to column index 1 (second column) as per user instruction if regex fails
    if name_idx == -1:
        if len(headers) >= 2:
            name_idx = 1
        else:
            return 0, 'لم يتم العثور على عمود اللقب والاسم'

    # Fallback for repeater index to column E (index 4) if not found by header
    if repeater_idx == -1 and len(headers) >= 5:
        repeater_idx = 4

    grades_created = 0
    # Process students starting from row index 6
    for row in rows[6:]:
        if len(row) <= name_idx: continue
        student_name = str(row[name_idx]).strip()
        if not student_name: continue

        # Find student
        student = None
        # Fast exact match
        for s in students_in_class:
            if s.full_name == student_name or f"{s.last_name} {s.first_name}" == student_name:
                student = s
                break

        # If not exact match, skip or try fuzzy (for now exact/reverse exact)
        if not student:
            parts = student_name.split()
            if len(parts) >= 2:
                rev_name = f"{parts[1]} {parts[0]}"
                for s in students_in_class:
                    if rev_name in s.full_name or s.full_name in student_name:
                        student = s
                        break

        if student:
            # Update Repeater Status
            if repeater_idx != -1 and len(row) > repeater_idx:
                rep_val = str(row[repeater_idx]).strip()
                is_repeater = bool(rep_val and rep_val not in ['0', 'لا', 'False', 'false', 'غ'])
                if student.is_repeater != is_repeater:
                    student.is_repeater = is_repeater
                    student.save(update_fields=['is_repeater'])

            for subject, col_idx in subject_indices.items():
                if len(row) > col_idx:
                    score_val = str(row[col_idx]).replace(',', '.').strip()
                    if score_val:
                        try:
                            # Handle explicit 'غ' or 'غائب' or 'غياب' as 0.0
                            if 'غ' in score_val.lower() or 'abs' in score_val.lower():
                                score = 0.0
                            else:
                                score = float(score_val)

                            # Update or create
                            Grade.objects.update_or_create(
                                student=student,
                                subject=subject,
                                term=term,
                                defaults={'score': score}
                            )
                            grades_created += 1
                        except ValueError:
                            pass # Ignore other empty or invalid strings

    return grades_created, f'تم استيراد {grades_created} علامة بنجاح للقسم {lvl} {cls}.'


def process_grades_file_ai(file_path, term):
    """
    Sends the extracted text from the Excel/PDF file to the LLM (AIService)
    to intelligently extract grades and student data into JSON format.
    """
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
                raw_text += " | ".join([str(c) for c in row if c]) + "\n"
    except Exception as e:
        return 0, f"خطأ في قراءة الملف محلياً قبل إرساله للذكاء الاصطناعي: {str(e)}"

    if not raw_text.strip():
        return 0, "الملف يبدو فارغاً."

    # 2. Construct AI Prompt
    system_prompt = """
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
"""

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
                    if isinstance(score, str) and ('غ' in score.lower() or 'abs' in score.lower()):
                        score_val = 0.0
                    else:
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
