
import re
from .models import Grade, Student, ClassAlias

def process_grades_file(file_path, term):
    from .import_utils import extract_rows_from_file
    from .mapping_views import resolve_class_alias

    with open(file_path, 'rb') as f:
        rows = list(extract_rows_from_file(f, override_filename=file_path))

    if not rows or len(rows) < 7:
        return 0, 'الملف فارغ أو لا يحتوي على بنية علامات صحيحة'

    # Robust Class Extraction: Scan the first 10 rows for patterns like 'أولى متوسط 1'
    lvl, cls = None, None
    class_name_raw = ""

    # Regex to capture Level (أولى/ثانية/ثالثة/رابعة) and Class Number (\d+)
    # It handles cases like "قسم: أولى متوسط 1", "أولى 1", etc.
    pattern = re.compile(r'(أولى|ثانية|ثالثة|رابعة)(?:\s+متوسط)?\s+(\d+)')

    for r_idx in range(min(10, len(rows))):
        for cell in rows[r_idx]:
            cell_str = str(cell).strip()
            match = pattern.search(cell_str)
            if match:
                class_name_raw = cell_str
                lvl = match.group(1) # e.g., 'أولى'
                cls = match.group(2) # e.g., '1'
                break
        if lvl and cls:
            break

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

    for idx, header in enumerate(headers):
        if header == 'اللقب والاسم' or header == 'الاسم واللقب':
            name_idx = idx
        elif header.endswith(suffix):
            # E.g. 'اللغة العربية ف 1' -> 'اللغة العربية'
            subject_name = header.replace(suffix, '').strip()
            subject_indices[subject_name] = idx
        elif header == avg_col_name:
            subject_indices['المعدل العام'] = idx

    if name_idx == -1:
        return 0, 'لم يتم العثور على عمود اللقب والاسم'

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
            for subject, col_idx in subject_indices.items():
                if len(row) > col_idx:
                    try:
                        score_val = str(row[col_idx]).replace(',', '.').strip()
                        if score_val:
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
                        pass # Ignore empty or invalid strings like 'غ' for absent

    return grades_created, f'تم استيراد {grades_created} علامة بنجاح للقسم {lvl} {cls}.'
