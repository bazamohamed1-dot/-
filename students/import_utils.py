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
    Scans the first 10 rows to identify column indices based on header names.
    Returns (header_indices, data_start_row).
    """
    header_indices = {}
    data_start_row = 0

    for i, row in enumerate(rows[:15]): # Check first 15 rows
        matches = 0
        current_map = {}
        for idx, cell in enumerate(row):
            cell_str = str(cell).strip()
            # Check for matches
            for key, field in header_map.items():
                if key in cell_str:
                    current_map[field] = idx
                    matches += 1
                    break # One field per column

        if matches >= threshold:
            header_indices = current_map
            data_start_row = i + 1
            break

    return header_indices, data_start_row

def parse_student_file(file_path):
    """
    Parses a student import file (Excel/HTML) and returns a list of dictionaries.
    """
    with open(file_path, 'rb') as f:
        rows = list(extract_rows_from_file(f))

    if not rows: return []

    # Map Arabic headers to model fields
    HEADER_MAP = {
        'رقم التعريف': 'student_id_number',
        'اللقب': 'last_name',
        'الاسم': 'first_name',
        'تاريخ الميلاد': 'date_of_birth',
        'تاريخ الازدياد': 'date_of_birth',
        'الجنس': 'gender',
        'مكان الميلاد': 'place_of_birth',
        'القسم': 'class_name',
        'السنة': 'academic_year',
        'المستوى': 'academic_year',
        'نظام التمدرس': 'attendance_system',
        'رقم القيد': 'enrollment_number',
        'تاريخ التسجيل': 'enrollment_date',
        'اسم الولي': 'guardian_name',
        'اسم الام': 'mother_name',
        'العنوان': 'address',
        'هاتف الولي': 'guardian_phone'
    }

    header_indices, data_start_row = detect_headers(rows, HEADER_MAP, threshold=3)

    # Fallback if detection fails (assume standard format)
    if not header_indices:
        header_indices = {
            'student_id_number': 1, 'last_name': 2, 'first_name': 3,
            'date_of_birth': 4, 'place_of_birth': 5, 'gender': 6,
            'academic_year': 7, 'class_name': 8, 'attendance_system': 10
        }
        data_start_row = 4 # Skip standard header rows

    students = []
    for i in range(data_start_row, len(rows)):
        row = rows[i]
        if not row: continue

        student_data = {}
        has_data = False

        for field, idx in header_indices.items():
            if idx < len(row):
                val = row[idx]
                if val and str(val).strip():
                    student_data[field] = str(val).strip()
                    has_data = True

        if has_data and 'student_id_number' in student_data:
            # Inference logic
            if 'academic_year' not in student_data and 'class_name' in student_data:
                cls = student_data['class_name']
                m = re.match(r'(\d+)', cls)
                if m:
                    lvl = m.group(1)
                    if 'M' in cls or 'AM' in cls:
                        student_data['academic_year'] = f"{lvl} متوسط"
                    else:
                        student_data['academic_year'] = lvl
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
        'تاريخ الازدياد': 'date_of_birth',
        'تاريخ الميلاد': 'date_of_birth',
        'مكان الازدياد': 'place_of_birth',
        'الرتبة': 'rank',
        'المادة': 'subject',
        'الدرجة': 'grade',
        'تاريخ السريان': 'effective_date',
        'الهاتف': 'phone',
        'البريد': 'email',
        'رقم': 'employee_code', # Generic for ID/Seq
        'الرمز': 'employee_code'
    }

    header_indices, data_start_row = detect_headers(rows, HEADER_MAP, threshold=3)

    # Fallback based on user image if detection fails
    if not header_indices:
        # 0:Seq, 1:Surname, 2:Name, 3:DOB, 6:Rank, 7:Subject...
        header_indices = {
            'employee_code': 0, 'last_name': 1, 'first_name': 2,
            'date_of_birth': 3, 'rank': 6, 'subject': 7,
            'grade': 8, 'effective_date': 9
        }
        data_start_row = 4 # The user said data starts at 4/5

    employees = []
    for i in range(data_start_row, len(rows)):
        row = rows[i]
        if not row: continue

        emp_data = {}

        for field, idx in header_indices.items():
            if idx < len(row):
                val = row[idx]
                # Clean up value
                if val:
                    emp_data[field] = str(val).strip()

        # Validation: Must have at least a Name
        if 'last_name' in emp_data or 'first_name' in emp_data:
            # Generate Code if missing
            if 'employee_code' not in emp_data:
                # Use row index as fallback code or simple hash
                ln = emp_data.get('last_name', '')
                fn = emp_data.get('first_name', '')
                emp_data['employee_code'] = f"{ln[:3]}{fn[:3]}{i}"

            employees.append(emp_data)

    return employees
