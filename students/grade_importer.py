
import re
from .models import Grade, Student, ClassAlias

def process_grades_file(file_path, term):
    from .import_utils import extract_rows_from_file
    from .mapping_views import resolve_class_alias

    with open(file_path, 'rb') as f:
        rows = list(extract_rows_from_file(f, override_filename=file_path))

    if not rows or len(rows) < 7:
        return 0, 'الملف فارغ أو لا يحتوي على بنية علامات صحيحة'

    # Extract class name from row 4, col 0 (index 3)
    class_name_raw = str(rows[3][0]) if len(rows[3]) > 0 else ''

    # Try to clean it. e.g. '... أولى متوسط 1 ...' -> 'أولى 1'
    # Actually, we can pass it directly to resolve_class_alias if it's exact,
    # but the image says 'أولى متوسط 1'. Let's do some cleaning.
    class_name_clean = class_name_raw
    if 'متوسط' in class_name_clean:
        class_name_clean = class_name_clean.replace('متوسط', '').strip()
        # Remove multiple spaces
        class_name_clean = re.sub(r'\s+', ' ', class_name_clean)

    # Let's resolve the class alias
    lvl, cls = resolve_class_alias(class_name_clean)
    if not lvl or not cls:
        # Fallback if the user hasn't mapped it, just try exact match
        parts = class_name_clean.split()
        if len(parts) >= 2:
            lvl = parts[0]
            cls = parts[1]
        else:
            return 0, f'تعذر تحديد القسم من الملف: {class_name_raw}'

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
