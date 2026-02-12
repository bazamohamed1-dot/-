import openpyxl
import xlrd
from bs4 import BeautifulSoup
from datetime import datetime

def parse_student_file(file_path):
    """
    Parses a student file (HTML, XLS, or XLSX) and returns a list of dictionaries
    ready for import via django-import-export.
    """

    # 1. Try HTML (bs4)
    try:
        data = parse_html(file_path)
        if data: return data
    except Exception:
        pass

    # 2. Try Excel .xls (xlrd)
    try:
        data = parse_xls(file_path)
        if data: return data
    except Exception:
        pass

    # 3. Try Excel .xlsx (openpyxl)
    try:
        data = parse_xlsx(file_path)
        if data: return data
    except Exception:
        pass

    return []

def parse_html(file_path):
    content = ""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return None

    if "<html" not in content.lower() and "<table" not in content.lower():
            return None

    soup = BeautifulSoup(content, 'html.parser')
    rows = soup.find_all('tr')
    return process_rows(rows, 'html')

def parse_xlsx(file_path):
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    return process_rows(ws.iter_rows(values_only=True), 'xlsx')

def parse_xls(file_path):
    wb = xlrd.open_workbook(file_path, formatting_info=False)
    ws = wb.sheet_by_index(0)
    rows = []
    for row_idx in range(ws.nrows):
        row = ws.row(row_idx)
        cols = []
        for c in row:
            if c.ctype == xlrd.XL_CELL_DATE:
                try:
                    val = xlrd.xldate.xldate_as_datetime(c.value, wb.datemode).strftime('%Y-%m-%d')
                except:
                    val = str(c.value)
            elif c.ctype == xlrd.XL_CELL_NUMBER:
                    val = str(int(c.value)) if c.value == int(c.value) else str(c.value)
            else:
                val = str(c.value).strip()
            cols.append(val)
        rows.append(cols)
    return process_rows(rows, 'xls')

def process_rows(rows, mode):
    processed_data = []
    processed_ids = set()

    for row in rows:
        try:
            # Normalize row to list of strings
            if mode == 'html':
                cells = row.find_all(['td', 'th'])
                cols = [c.get_text(strip=True) for c in cells]
            else:
                cols = [str(c).strip() if c is not None else '' for c in row]

            # Filter valid rows (Student ID must be digit)
            if not cols or len(cols) < 14: continue

            sid = cols[0]
            if not sid.isdigit(): continue # Skip headers

            if sid in processed_ids: continue
            processed_ids.add(sid)

            # Extract Data
            dob = parse_date(cols[4])
            enroll_date = parse_date(cols[14]) if len(cols) > 14 else datetime.now().date()

            level = cols[10]
            class_code = cols[11]
            full_class = f"{level} {class_code}".strip()

            student_data = {
                'student_id_number': sid,
                'last_name': cols[1],
                'first_name': cols[2],
                'gender': cols[3],
                'date_of_birth': dob,
                'place_of_birth': cols[9],
                'academic_year': level,
                'class_name': full_class,
                'attendance_system': cols[12],
                'enrollment_number': cols[13],
                'enrollment_date': enroll_date,
            }
            processed_data.append(student_data)

        except Exception:
            continue

    return processed_data

def parse_date(date_str):
    if not date_str or str(date_str).lower() in ['none', 'nan', '']:
            return datetime(1900, 1, 1).date()

    # Handle Excel Serial Date
    if str(date_str).replace('.', '', 1).isdigit():
            try:
                val = float(date_str)
                if val > 10000:
                    return datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(val) - 2).date()
            except: pass

    date_str = str(date_str).strip().split(' ')[0] # Remove time
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y', '%Y.%m.%d'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return datetime(1900, 1, 1).date()
