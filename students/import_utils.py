import openpyxl
import xlrd
from bs4 import BeautifulSoup
from datetime import datetime, date
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Level Normalization Map
LEVEL_MAP = {
    'أولى': '1AM', 'اولى': '1AM', '1am': '1AM', '1': '1AM',
    'ثانية': '2AM', 'ثانية': '2AM', '2am': '2AM', '2': '2AM',
    'ثالثة': '3AM', 'ثالثة': '3AM', '3am': '3AM', '3': '3AM',
    'رابعة': '4AM', 'رابعة': '4AM', '4am': '4AM', '4': '4AM',
    'أولى متوسط': '1AM', 'ثانية متوسط': '2AM', 'ثالثة متوسط': '3AM', 'رابعة متوسط': '4AM'
}

# Column Headers Mapping (Arabic, French, English)
HEADER_MAP = {
    'student_id_number': ['رقم التعريف', 'id', 'student_id', 'matricule', 'رقم التسجيل', 'رقم'],
    'last_name': ['اللقب', 'last_name', 'nom', 'surname', 'family_name'],
    'first_name': ['الاسم', 'first_name', 'prenom', 'given_name'],
    'gender': ['الجنس', 'gender', 'sexe', 'sex'],
    'date_of_birth': ['تاريخ الميلاد', 'date_of_birth', 'dob', 'date_naissance', 'tarihk_milad', 'تاريخ الازدياد'],
    'place_of_birth': ['مكان الميلاد', 'place_of_birth', 'pob', 'lieu_naissance', 'makan_milad', 'مكان الازدياد'],
    'academic_year': ['المستوى', 'academic_year', 'level', 'niveau', 'annee_scolaire', 'السنة الدراسية', 'السنة'],
    'class_name': ['القسم', 'class_name', 'class', 'classe', 'fawj', 'الفوج التربوي', 'الفوج'],
    'attendance_system': ['نظام التمدرس', 'attendance_system', 'system', 'regime', 'nizam', 'النظام'],
    'enrollment_number': ['رقم القيد', 'enrollment_number', 'enroll_num', 'numero_inscription', 'raqm_kaid'],
    'enrollment_date': ['تاريخ التسجيل', 'enrollment_date', 'date_inscription', 'tarihk_tasjil', 'تاريخ الدخول'],
    'guardian_name': ['اسم الولي', 'guardian_name', 'tuteur', 'wali', 'الولي'],
    'mother_name': ['اسم الأم', 'mother_name', 'mere', 'oum', 'لقب واسم الأم'],
    'address': ['العنوان', 'address', 'adresse', 'sakan', 'مقر السكن'],
    'guardian_phone': ['رقم الهاتف', 'phone', 'telephone', 'mobile', 'hatif', 'رقم الولي']
}

def parse_student_file(file_path):
    """
    Parses a student file (HTML, XLS, or XLSX) and returns a list of dictionaries
    ready for import via django-import-export.
    """
    logger.info(f"Starting parsing for file: {file_path}")

    # 1. Try HTML (bs4)
    try:
        data = parse_html(file_path)
        if data:
            logger.info(f"Successfully parsed as HTML with {len(data)} records.")
            return data
    except Exception as e:
        logger.warning(f"HTML parsing failed: {e}")

    # 2. Try Excel .xls (xlrd)
    try:
        data = parse_xls(file_path)
        if data:
            logger.info(f"Successfully parsed as XLS with {len(data)} records.")
            return data
    except Exception as e:
        logger.warning(f"XLS parsing failed: {e}")

    # 3. Try Excel .xlsx (openpyxl)
    try:
        data = parse_xlsx(file_path)
        if data:
            logger.info(f"Successfully parsed as XLSX with {len(data)} records.")
            return data
    except Exception as e:
        logger.warning(f"XLSX parsing failed: {e}")

    logger.error("All parsing methods failed or returned no data.")
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

def normalize_header(header):
    if not header: return ""
    return str(header).strip().lower().replace('_', ' ').replace('-', ' ')

def detect_columns(header_row):
    """
    Returns a dict mapping field_name -> column_index
    """
    col_map = {}
    used_indices = set()

    for idx, col in enumerate(header_row):
        val = normalize_header(col)
        if not val: continue

        # Check against HEADER_MAP
        for field, keywords in HEADER_MAP.items():
            if field in col_map: continue # Already found

            # Exact or fuzzy match
            for kw in keywords:
                if kw in val:
                    col_map[field] = idx
                    used_indices.add(idx)
                    break

    return col_map

def process_rows(rows, mode):
    processed_data = []
    processed_ids = set()

    # Identify Headers
    header_row = None
    col_map = {}
    data_rows = []

    # Iterate to find header row (first row with enough string columns)
    iterator = iter(rows)

    for row in iterator:
        # Convert row to list of strings
        if mode == 'html':
            cells = row.find_all(['td', 'th'])
            cols = [c.get_text(strip=True) for c in cells]
        else:
            cols = [str(c).strip() if c is not None else '' for c in row]

        # Check if this is a potential header row
        # Heuristic: Contains "Name" or "ID" or "Nom" or "Matricule"
        is_header = False
        temp_map = detect_columns(cols)

        # If we found at least 3 recognizable columns (ID, Name, DOB usually), assume it's a header
        if len(temp_map) >= 3:
            col_map = temp_map
            is_header = True
            # Consume rest of iterator into data_rows
            break

        # If not header, maybe data? Wait, we need headers first.
        # But for files without headers (legacy support), we might fallback.
        # Let's collect rows just in case we default to fixed index.
        data_rows.append(cols)

    # Continue iterator for data
    for row in iterator:
        if mode == 'html':
            cells = row.find_all(['td', 'th'])
            cols = [c.get_text(strip=True) for c in cells]
        else:
            cols = [str(c).strip() if c is not None else '' for c in row]
        data_rows.append(cols)

    # Fallback for Fixed Indices (Legacy Support) if header detection failed
    if not col_map:
        # Default mapping based on previous hardcoded indices
        col_map = {
            'student_id_number': 0,
            'last_name': 1,
            'first_name': 2,
            'gender': 3,
            'date_of_birth': 4,
            'place_of_birth': 9,
            'academic_year': 10,
            'class_name': 11,
            'attendance_system': 12,
            'enrollment_number': 13,
            'enrollment_date': 14
        }
        logger.warning("Header detection failed. Using default column indices.")

    row_count = 0
    for cols in data_rows:
        row_count += 1
        try:
            if not cols: continue

            # Get ID
            idx_id = col_map.get('student_id_number', 0)
            if idx_id >= len(cols): continue

            sid = cols[idx_id]
            if not sid.isdigit(): continue # Skip empty or invalid lines

            if sid in processed_ids: continue
            processed_ids.add(sid)

            # Helper to safely get value
            def get_val(field, default=""):
                idx = col_map.get(field)
                if idx is not None and idx < len(cols):
                    return cols[idx]
                return default

            # Extract Data
            last_name = get_val('last_name')
            first_name = get_val('first_name')
            gender = get_val('gender')
            dob = parse_date(get_val('date_of_birth'))
            pob = get_val('place_of_birth')

            raw_level = get_val('academic_year')
            # Normalize Level
            level = raw_level
            for k, v in LEVEL_MAP.items():
                if k in str(raw_level).strip():
                    level = v
                    break

            class_code = get_val('class_name')

            # Smart Class Name Construction
            full_class = ""
            if class_code:
                # If class already contains the normalized level (e.g. "1AM 1")
                if level and level in class_code:
                    full_class = class_code
                # If class contains the RAW level (e.g. "أولى 1") -> normalize it
                elif raw_level and raw_level in class_code and raw_level != level:
                     full_class = class_code.replace(raw_level, level).strip()
                elif level:
                     full_class = f"{level} {class_code}".strip()
                else:
                    full_class = class_code

            attendance_sys = get_val('attendance_system', "نصف داخلي")
            enroll_num = get_val('enrollment_number')
            enroll_date = parse_date(get_val('enrollment_date', datetime.now().date()))

            student_data = {
                'student_id_number': sid,
                'last_name': last_name,
                'first_name': first_name,
                'gender': gender,
                'date_of_birth': dob,
                'place_of_birth': pob,
                'academic_year': level,
                'class_name': full_class,
                'attendance_system': attendance_sys,
                'enrollment_number': enroll_num,
                'enrollment_date': enroll_date,
            }
            processed_data.append(student_data)

        except Exception as e:
            logger.error(f"Error processing row {row_count}: {e}")
            continue

    return processed_data

def parse_date(date_str):
    if not date_str or str(date_str).lower() in ['none', 'nan', '']:
            return datetime(1900, 1, 1).date()

    if isinstance(date_str, datetime) or isinstance(date_str, date):
        return date_str

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
