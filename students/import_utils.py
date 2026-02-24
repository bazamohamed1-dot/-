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
    # Check if file has 'name' attribute (e.g. Django UploadedFile)
    filename = getattr(file, 'name', 'unknown').lower()

    if filename.endswith('.xlsx'):
        try:
            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                yield list(row)
        except:
            # Fallback for HTML disguised as XLSX
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
             # Fallback for HTML disguised as XLS
            yield from _parse_html_table(content)

    elif filename.endswith('.docx'):
        doc = Document(file)
        for table in doc.tables:
            for row in table.rows:
                yield [cell.text.strip() for cell in row.cells]

    elif filename.endswith('.pdf'):
        # PDF is hard to get "rows", return parsing results as pseudo-rows
        # This is a best-effort for simple tables
        reader = PdfReader(file)
        for page in reader.pages:
            text = page.extract_text()
            for line in text.split('\n'):
                yield line.split() # Naive split

    elif filename.endswith('.html') or filename.endswith('.htm'):
        content = file.read()
        yield from _parse_html_table(content)

    else:
        # Try as generic text or HTML if extension is unknown but content is provided
        try:
            file.seek(0)
            content = file.read()
            # Heuristic: does it look like HTML?
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

def parse_student_file(file_path):
    """
    Parses a student import file (Excel/HTML) and returns a list of dictionaries.
    Uses extract_rows_from_file internally.
    """
    students = []

    # Open file in binary mode
    with open(file_path, 'rb') as f:
        # extract_rows_from_file expects an object with .name
        # We wrap it or just rely on file path if needed, but the util uses .name
        # Let's mock a name if needed, or pass the file object if it has one.
        # Since we opened it from disk, f.name works.
        rows = list(extract_rows_from_file(f))

    if not rows:
        return []

    # Detect Headers
    # Map common Arabic headers to model fields
    HEADER_MAP = {
        'رقم التعريف': 'student_id_number',
        'اللقب': 'last_name',
        'الاسم': 'first_name',
        'تاريخ الميلاد': 'date_of_birth',
        'تاريخ الازدياد': 'date_of_birth',
        'الجنس': 'gender',
        'مكان الميلاد': 'place_of_birth',
        'القسم': 'class_name',
        'السنة': 'academic_year', # Point 1: Map "السنة" to academic_year
        'المستوى': 'academic_year',
        'صفة التمدرس': 'attendance_system',
        'نظام التمدرس': 'attendance_system',
        'رقم القيد': 'enrollment_number',
        'تاريخ التسجيل': 'enrollment_date',
        'اسم الولي': 'guardian_name',
        'اسم الام': 'mother_name',
        'العنوان': 'address',
        'هاتف الولي': 'guardian_phone'
    }

    header_indices = {}
    data_start_row = 0

    # Try to find header row (first row with >3 matching columns)
    for i, row in enumerate(rows[:10]): # Search first 10 rows
        matches = 0
        current_map = {}
        for idx, cell in enumerate(row):
            cell_str = str(cell).strip()
            # Fuzzy match or exact match
            for key, field in HEADER_MAP.items():
                if key in cell_str:
                    current_map[field] = idx
                    matches += 1
                    break

        if matches >= 3: # Threshold
            header_indices = current_map
            data_start_row = i + 1
            break

    # If no header found, use default indices (Fallback for legacy exports)
    if not header_indices:
        # Fallback 1: Standard Ministry HTML Export Order
        # 0: Seq, 1: ID, 2: Surname, 3: Name, 4: DOB, 5: POB, 6: Sex, 7: Year, 8: Class...
        header_indices = {
            'student_id_number': 1,
            'last_name': 2,
            'first_name': 3,
            'date_of_birth': 4,
            'place_of_birth': 5,
            'gender': 6,
            'academic_year': 7, # "السنة"
            'class_name': 8,
            'attendance_system': 10
        }
        data_start_row = 0 # Assume no header or skipped in caller?
        # Actually standard exports usually have header. If we missed it, maybe it's not there.
        pass

    # Extract Data
    for i in range(data_start_row, len(rows)):
        row = rows[i]
        if not row: continue

        student_data = {}
        has_data = False

        for field, idx in header_indices.items():
            if idx < len(row):
                val = row[idx]
                if val:
                    student_data[field] = str(val).strip()
                    has_data = True

        if has_data and 'student_id_number' in student_data:
            # Post-process
            # Infer level from class if year missing
            if 'academic_year' not in student_data and 'class_name' in student_data:
                cls = student_data['class_name']
                # Try extract "1" from "1AM" or "1M"
                import re
                m = re.match(r'(\d+)', cls)
                if m:
                    lvl = m.group(1)
                    if 'M' in cls or 'AM' in cls:
                        student_data['academic_year'] = f"{lvl} متوسط"
                    else:
                        student_data['academic_year'] = lvl

            students.append(student_data)

    return students
