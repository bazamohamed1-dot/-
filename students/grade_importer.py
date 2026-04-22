
import re
from .models import Grade, Student, ClassAlias

def process_grades_file(file_path, term, subject_mappings=None):
    from .import_utils import extract_rows_from_file
    from .mapping_views import resolve_class_alias
    from .school_year_utils import get_current_school_year

    academic_year = get_current_school_year()
    with open(file_path, 'rb') as f:
        rows = list(extract_rows_from_file(f, override_filename=file_path))

    if not rows or len(rows) < 7:
        return 0, 'الملف فارغ أو لا يحتوي على بنية علامات صحيحة'

    import os
    # Robust Class Extraction: Scan the first 10 rows for patterns like 'أولى متوسط 1' or '1م1'
    lvl, cls = None, None
    class_code = None
    class_name_raw = ""

    # Regex to capture Level (أولى/ثانية/ثالثة/رابعة) and Class Number (\d+)
    # It handles cases like "قسم: أولى متوسط 1", "أولى 1", "رابعة متوسط 01" etc.
    pattern = re.compile(r'(أولى|ثانية|ثالثة|رابعة)(?:\s+متوسط)?\s*[-_]?\s*(\d+)')
    # Regex for class codes like '1م1', '1AM1', '1 م 1'
    code_pattern = re.compile(r'([1234])\s*(?:م|متوسط|AM)\s*(\d+)', re.IGNORECASE)

    for r_idx in range(min(10, len(rows))):
        for cell in rows[r_idx]:
            cell_str = str(cell).strip()

            # Check for standard arabic name first
            match = pattern.search(cell_str)
            if match:
                class_name_raw = cell_str
                lvl = match.group(1) # e.g., 'أولى'
                cls = str(int(match.group(2))) # e.g., '1'
                break

            # Then check for class code format
            code_match = code_pattern.search(cell_str)
            if code_match:
                class_name_raw = cell_str
                lvl_digit = code_match.group(1)
                cls = str(int(code_match.group(2)))
                arb_map = {'1': 'أولى', '2': 'ثانية', '3': 'ثالثة', '4': 'رابعة'}
                lvl = arb_map.get(lvl_digit, lvl_digit)
                class_code = f"{lvl_digit}م{cls}"
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
        else:
            code_match = code_pattern.search(filename)
            if code_match:
                class_name_raw = filename
                lvl_digit = code_match.group(1)
                cls = str(int(code_match.group(2)))
                arb_map = {'1': 'أولى', '2': 'ثانية', '3': 'ثالثة', '4': 'رابعة'}
                lvl = arb_map.get(lvl_digit, lvl_digit)
                class_code = f"{lvl_digit}م{cls}"

    # If regex failed, maybe it's in a known Alias format in the first cell of row 4 or 5
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
        return 0, f'تعذر تحديد القسم (المستوى والرقم) من الملف. تأكد من وجود اسم القسم مثل "أولى متوسط 1" أو "1م1". النص الذي تم قراءته: {class_name_raw}'

    # Ensure class exists in our DB. Check by level+class or class_code.
    from django.db.models import Q

    # Try creating a class code if we don't have one but have lvl and cls
    if not class_code:
        lvl_digit = ""
        if "أولى" in lvl or "1" in lvl: lvl_digit = "1"
        elif "ثانية" in lvl or "2" in lvl: lvl_digit = "2"
        elif "ثالثة" in lvl or "3" in lvl: lvl_digit = "3"
        elif "رابعة" in lvl or "4" in lvl: lvl_digit = "4"
        if lvl_digit:
            class_code = f"{lvl_digit}م{cls}"

    students_in_class = Student.objects.filter(
        Q(academic_year=lvl, class_name=cls) |
        Q(class_code=class_code)
    )

    if not students_in_class.exists():
        return 0, f'القسم {lvl} {cls} (الرمز {class_code}) غير موجود أو لا يحتوي على تلاميذ.'

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


    # Map Subject Name -> (Column Index, Term)
    # Allows storing multiple terms from the same file
    # Format: {(subject_name, term): col_idx}
    subject_indices_multi = {}
    name_idx = -1
    repeater_idx = -1

    import difflib
    from .models_mapping import SubjectAlias

    known_subjects = [
        'اللغة العربية', 'الرياضيات', 'العلوم الفيزيائية', 'الفيزياء', 'علوم الطبيعة والحياة', 'العلوم الطبيعية',
        'التربية الإسلامية', 'التربية المدنية', 'التاريخ والجغرافيا', 'التاريخ', 'الجغرافيا',
        'اللغة الفرنسية', 'الفرنسية', 'اللغة الإنجليزية', 'الإنجليزية', 'اللغة الأمازيغية', 'الأمازيغية',
        'التربية الفنية', 'الفنية', 'الرسم', 'التربية الموسيقية', 'الموسيقى', 'التربية البدنية', 'التربية البدنية والرياضية', 'ت البدنية والرياضية', 'الرياضة',
        'الإعلام الآلي', 'المعلوماتية', 'ع الطبيعة والحياة', 'ع الفيزيائية والتكنولوجيا', 'التربية التشكيلية'
    ]

    # Map numbers to Term Strings
    term_map = {
        '1': 'الفصل الأول',
        '2': 'الفصل الثاني',
        '3': 'الفصل الثالث'
    }

    # Fetch dynamic aliases from DB
    db_aliases = {alias.alias: alias.canonical_name for alias in SubjectAlias.objects.all()}
    # أعمدة ليست مواداً (معلومات التلميذ لا تُعتبر مواداً)
    non_subjects = [
        'الرقم', 'رقم', 'الملاحظة', 'التقدير', 'الغياب', 'المواظبة',
        'اللقبوالاسم', 'الاسمواللقب', 'المجموع', 'المعدل', 'معدل', 'المجموع العام', 'القرار',
        'الجنس', 'النوع', 'تاريخ الميلاد', 'تاريخ الازدياد', 'الميلاد', 'تاريخ'
    ]

    for idx, header in enumerate(headers):
        original_header = header.replace('\n', ' ').replace('\r', '').strip()
        clean_header = re.sub(r'(ف|الفصل)\s*\d+', '', original_header).strip()

        # عمود "معدل الفصل 1/2/3" يجب أن يُستورد كمادة مرجعية للمعدل (مطابقة لملف Excel)
        # ملاحظة: لا نعتمد على clean_header هنا لأنه قد يصبح "معدل" فقط بعد التنظيف.
        m_avg = re.search(r'معدل\s*الفصل\s*([123])', original_header)
        if m_avg:
            tnum = m_avg.group(1)
            col_term = term_map.get(tnum, term)
            subject_indices_multi[('المعدل العام', col_term)] = idx
            continue

        # If user provided mappings via UI, use those explicitly.
        # Otherwise, fall back to database aliases and fuzzy matching.
        mapped_subject = None
        if subject_mappings and clean_header in subject_mappings:
            mapped_subject = subject_mappings[clean_header]
            if mapped_subject == "ignore":
                continue
            # احتفاظ بنفس الاسم: نستخدم اسم المادة من الملف كما هو (المفتاح في الخريطة)
            if mapped_subject in ("--احتفاظ بنفس الاسم--", ""):
                mapped_subject = clean_header

        if not mapped_subject:
            # Apply Subject Aliases
            if clean_header in db_aliases:
                clean_header = db_aliases[clean_header]
            mapped_subject = clean_header

        if 'اللقب' in mapped_subject or 'الاسم' in mapped_subject or 'الاسم واللقب' in mapped_subject or 'اللقب والاسم' in mapped_subject:
            if name_idx == -1:
                name_idx = idx
        elif 'الإعادة' in mapped_subject or 'الاعادة' in mapped_subject:
            repeater_idx = idx
        else:
            # Determine the explicit term for this column if it exists
            match_term = re.search(r'(ف|الفصل)\s*(\d+)', original_header)
            col_term = term_map.get(match_term.group(2)) if match_term else term

            if 'المعدل العام' in mapped_subject or 'معدل الفصل' in mapped_subject:
                subject_indices_multi[('المعدل العام', col_term)] = idx
            else:
                if subject_mappings and clean_header in subject_mappings:
                    # نستخدم الاسم كما حدده المستخدم أو اسم الملف كما هو عند "احتفاظ بنفس الاسم"
                    final_subject = (mapped_subject or clean_header).strip()
                else:
                    matches = difflib.get_close_matches(mapped_subject, known_subjects, n=1, cutoff=0.85)
                    final_subject = matches[0] if matches else mapped_subject

                if final_subject and len(final_subject) > 3 and final_subject not in non_subjects:
                    subject_indices_multi[(final_subject, col_term)] = idx

    if len(subject_indices_multi) == 0:
        for idx in range(5, min(19, len(headers))):
            header = headers[idx]
            original_header = header.replace('\n', ' ').strip()
            clean_header = re.sub(r'ف\s*\d+', '', original_header).strip()

            mapped_subject = None
            if subject_mappings and clean_header in subject_mappings:
                mapped_subject = subject_mappings[clean_header]
                if mapped_subject == "ignore":
                    continue
                if mapped_subject in ("--احتفاظ بنفس الاسم--", ""):
                    mapped_subject = clean_header

            if not mapped_subject:
                if clean_header in db_aliases:
                    clean_header = db_aliases[clean_header]
                mapped_subject = clean_header

            match_term = re.search(r'(ف|الفصل)\s*(\d+)', original_header)
            col_term = term_map.get(match_term.group(2)) if match_term else term

            if 'المعدل العام' in mapped_subject or 'معدل الفصل' in mapped_subject:
                subject_indices_multi[('المعدل العام', col_term)] = idx
            elif mapped_subject and mapped_subject != '' and len(mapped_subject) > 2 and mapped_subject not in non_subjects:
                subject_indices_multi[(mapped_subject.strip(), col_term)] = idx

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
    # Process students starting from row index 6 — تجاهل السطر الأخير إذا كان "معدل المواد" (خلايا مدمجة)
    data_rows = rows[6:]
    for row in data_rows:
        if len(row) <= name_idx: continue
        student_name = str(row[name_idx]).strip()
        if not student_name: continue
        # استغناء تام عن سطر "معدل المواد" في نهاية الجدول (لا يُستورد ولا يُستخدم في أي حساب)
        if 'معدل المواد' in student_name or student_name.strip() in ('معدل المواد', 'معدل المادة', 'المعدل العام للمواد'):
            continue

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

            for (subject, sub_term), col_idx in subject_indices_multi.items():
                if len(row) > col_idx:
                    score_val = str(row[col_idx]).replace(',', '.').strip()
                    if score_val:
                        try:
                            # Handle explicit 'غ' or 'غائب' or 'غياب' as -1.0 (to mean absent without throwing it away)
                            if 'غ' in score_val.lower() or 'abs' in score_val.lower():
                                score = -1.0
                            else:
                                score = float(score_val)

                            # Update or create using the specific term found for this column
                            Grade.objects.update_or_create(
                                student=student,
                                subject=subject,
                                term=sub_term,
                                academic_year=academic_year,
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

    from .school_year_utils import get_current_school_year
    academic_year = get_current_school_year()
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
                        score_val = -1.0
                    else:
                        score_val = float(score)

                    Grade.objects.update_or_create(
                        student=student,
                        subject=subject,
                        term=term,
                        academic_year=academic_year,
                        defaults={'score': score_val}
                    )
                    grades_created += 1
                except (ValueError, TypeError):
                    pass

    return grades_created, f"تم استيراد {grades_created} علامة بنجاح للقسم {lvl} {cls} باستخدام الذكاء الاصطناعي."
