import openpyxl
import xlrd
from bs4 import BeautifulSoup
from docx import Document
from PyPDF2 import PdfReader
import re
from datetime import datetime, date

def extract_rows_from_file(file):
    """
    Extracts rows from any supported file type (Excel, Word, HTML, PDF).
    Returns a generator of lists.
    """
    file.seek(0)
    filename = getattr(file, 'name', 'unknown').lower()

    if filename.endswith('.xlsx'):
        try:
            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                yield list(row)
        except:
            file.seek(0)
            content = file.read()
            yield from _parse_html_table(content)

    elif filename.endswith('.xls'):
        try:
            content = file.read()
            wb = xlrd.open_workbook(file_contents=content)
            sheet = wb.sheet_by_index(0)
            for r in range(sheet.nrows):
                yield sheet.row_values(r)
        except:
            yield from _parse_html_table(content)

    elif filename.endswith('.docx'):
        doc = Document(file)
        for table in doc.tables:
            for row in table.rows:
                yield [cell.text.strip() for cell in row.cells]

    elif filename.endswith('.pdf'):
        reader = PdfReader(file)
        for page in reader.pages:
            text = page.extract_text()
            for line in text.split('\n'):
                yield line.split()

    elif filename.endswith('.html') or filename.endswith('.htm'):
        content = file.read()
        yield from _parse_html_table(content)

    else:
        try:
            file.seek(0)
            content = file.read()
            if b'<html' in content.lower() or b'<table' in content.lower():
                yield from _parse_html_table(content)
        except:
            pass

def _parse_html_table(content):
    soup = BeautifulSoup(content, 'html.parser')
    table = soup.find('table')
    if table:
        for tr in table.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            yield [cell.get_text(strip=True) for cell in cells]

def detect_headers(rows, header_map, threshold=3):
    """
    Scans the first 15 rows to identify column indices based on header names.
    Returns (header_indices, data_start_row).
    """
    header_indices = {}
    data_start_row = 0
    best_match_count = 0
    best_row_idx = -1

    for i, row in enumerate(rows[:15]): # Check first 15 rows
        matches = 0
        current_map = {}

        # Normalize row content for easier matching
        row_str = [str(cell).strip() if cell else "" for cell in row]

        # Check every cell against every keyword
        for idx, cell_str in enumerate(row_str):
            if not cell_str: continue

            for key, field in header_map.items():
                # Flexible matching: key in cell or cell in key (if cell is short)
                # We prioritize explicit containment
                if key in cell_str:
                    current_map[field] = idx
                    matches += 1
                    # Do NOT break here, allows multiple fields per column (e.g. "Name Surname")

        # Heuristic: If we found more matches than previous best, keep it
        if matches > best_match_count:
            best_match_count = matches
            header_indices = current_map
            best_row_idx = i

        # Heuristic: If we found a very strong match (threshold), stop early?
        # Maybe not, user says headers vary. Best to scan all 15 and pick winner.

    if best_match_count >= threshold:
        data_start_row = best_row_idx + 1
        return header_indices, data_start_row

    return {}, 0

def parse_student_file(file_path):
    """
    Parses a student import file (Excel/HTML) and returns a list of dictionaries.
    """
    with open(file_path, 'rb') as f:
        rows = list(extract_rows_from_file(f))

    if not rows: return []

    # Map Arabic headers to model fields
    # Expanded keywords for robustness
    HEADER_MAP = {
        'رقم التعريف': 'student_id_number',
        'اللقب': 'last_name',
        'الاسم': 'first_name',
        'اسم و لقب': 'full_name', # Special key for merging
        'اللقب و الاسم': 'full_name',
        'تاريخ الميلاد': 'date_of_birth',
        'تاريخ الازدياد': 'date_of_birth',
        'الجنس': 'gender',
        'مكان الميلاد': 'place_of_birth',
        'القسم': 'class_name',
        'فوج': 'class_name',
        'السنة': 'academic_year',
        'المستوى': 'academic_year',
        'نظام التمدرس': 'attendance_system',
        'النظام': 'attendance_system',
        'رقم القيد': 'enrollment_number',
        'تاريخ التسجيل': 'enrollment_date',
        'اسم الولي': 'guardian_name',
        'اسم الام': 'mother_name',
        'العنوان': 'address',
        'هاتف الولي': 'guardian_phone'
    }

    header_indices, data_start_row = detect_headers(rows, HEADER_MAP, threshold=2) # Lower threshold slightly

    # Fallback if detection fails (assume standard format)
    if not header_indices:
        # Standard format assumption (fallback)
        header_indices = {
            'student_id_number': 1, 'last_name': 2, 'first_name': 3,
            'date_of_birth': 4, 'place_of_birth': 5, 'gender': 6,
            'academic_year': 7, 'class_name': 8, 'attendance_system': 10
        }
        data_start_row = 4

    students = []

    # Check if we have a "Shared Column" situation
    shared_name_col = False
    if header_indices.get('last_name') == header_indices.get('first_name') and header_indices.get('last_name') is not None:
        shared_name_col = True

    # Check for "Full Name" key
    if 'full_name' in header_indices:
        shared_name_col = True
        # Map it to last_name for extraction, then split
        if 'last_name' not in header_indices:
            header_indices['last_name'] = header_indices['full_name']
            header_indices['first_name'] = header_indices['full_name']

    for i in range(data_start_row, len(rows)):
        row = rows[i]
        if not row: continue

        student_data = {}
        has_data = False

        for field, idx in header_indices.items():
            if field == 'full_name': continue # processed via shared logic

            if idx < len(row):
                val = row[idx]
                if val and str(val).strip():
                    student_data[field] = str(val).strip()
                    has_data = True

        # Post-process Shared Name Column
        if shared_name_col and 'last_name' in student_data:
            full_val = student_data['last_name']
            # Heuristic split: Last Name usually first in Arabic lists? Or check logic.
            # "اللقب والاسم" -> Surname Name
            parts = full_val.split(None, 1) # Split on first whitespace
            if len(parts) > 1:
                student_data['last_name'] = parts[0]
                student_data['first_name'] = parts[1]
            else:
                student_data['last_name'] = parts[0]
                student_data['first_name'] = "" # Or duplicate? keeping empty safer

        if has_data and 'student_id_number' in student_data:
            # Inference logic
            if 'academic_year' not in student_data and 'class_name' in student_data:
                cls = student_data['class_name']
                # Normalize Class Name (remove extra spaces)
                cls = " ".join(cls.split())
                student_data['class_name'] = cls

                m = re.match(r'(\d+)', cls)
                if m:
                    lvl = m.group(1)
                    if 'M' in cls or 'AM' in cls:
                        student_data['academic_year'] = f"{lvl} متوسط"
                    else:
                        student_data['academic_year'] = lvl

            # Additional cleanup
            if 'date_of_birth' in student_data:
                # Handle Excel Serial Date if needed, or string formats
                pass # Already str() above, parser handles strings usually

            students.append(student_data)

    return students

def parse_hr_file(file_path):
    """
    Parses an employee/HR import file using smart header detection.
    """
    with open(file_path, 'rb') as f:
        rows = list(extract_rows_from_file(f))

    if not rows: return []

    HEADER_MAP = {
        'اللقب': 'last_name',
        'الاسم': 'first_name',
        'الاسم واللقب': 'full_name',
        'تاريخ الازدياد': 'date_of_birth',
        'تاريخ الميلاد': 'date_of_birth',
        'مكان الازدياد': 'place_of_birth',
        'الرتبة': 'rank',
        'المادة': 'subject',
        'الدرجة': 'grade',
        'تاريخ السريان': 'effective_date',
        'الهاتف': 'phone',
        'البريد': 'email',
        'رقم': 'employee_code',
        'الرمز': 'employee_code'
    }

    header_indices, data_start_row = detect_headers(rows, HEADER_MAP, threshold=3)

    if not header_indices:
        header_indices = {
            'employee_code': 0, 'last_name': 1, 'first_name': 2,
            'date_of_birth': 3, 'rank': 6, 'subject': 7,
            'grade': 8, 'effective_date': 9
        }
        data_start_row = 4

    employees = []

    shared_name_col = False
    if header_indices.get('last_name') == header_indices.get('first_name') and header_indices.get('last_name') is not None:
        shared_name_col = True
    if 'full_name' in header_indices:
        shared_name_col = True
        if 'last_name' not in header_indices:
            header_indices['last_name'] = header_indices['full_name']
            header_indices['first_name'] = header_indices['full_name']

    for i in range(data_start_row, len(rows)):
        row = rows[i]
        if not row: continue

        emp_data = {}

        for field, idx in header_indices.items():
            if field == 'full_name': continue
            if idx < len(row):
                val = row[idx]
                if val:
                    emp_data[field] = str(val).strip()

        # Post-process Shared Name Column
        if shared_name_col and 'last_name' in emp_data:
            full_val = emp_data['last_name']
            parts = full_val.split(None, 1)
            if len(parts) > 1:
                emp_data['last_name'] = parts[0]
                emp_data['first_name'] = parts[1]
            else:
                emp_data['last_name'] = parts[0]
                emp_data['first_name'] = ""

        if 'last_name' in emp_data or 'first_name' in emp_data:
            if 'employee_code' not in emp_data:
                ln = emp_data.get('last_name', '')
                fn = emp_data.get('first_name', '')
                emp_data['employee_code'] = f"{ln[:3]}{fn[:3]}{i}"

            employees.append(emp_data)

    return employees
