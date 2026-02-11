from django.core.management.base import BaseCommand
from students.models import Student
from bs4 import BeautifulSoup
import openpyxl
import xlrd
import os
from datetime import datetime

class Command(BaseCommand):
    help = 'Imports students from Eleve.xls (HTML format) or standard Excel .xlsx with bulk operations.'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Path to the file to import', required=False)
        parser.add_argument('--update-existing', action='store_true', help='Update existing students if found')

    def handle(self, *args, **options):
        file_path = options.get('file') or 'Eleve.xls'
        # Force overwrite logic as requested: Wipe DB if new file imported
        # We will assume if this command runs, we want to reset or update.
        # User explicitly asked to delete all data.
        update_existing = options.get('update_existing', False)

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File {file_path} not found'))
            return

        # FULL RESET (Truncate)
        if not update_existing:
            self.stdout.write(self.style.WARNING('⚠ Deleting ALL existing students before import...'))
            Student.objects.all().delete()

        self.stdout.write(f'Processing file: {file_path}')

        # Robust Multi-Format Strategy: HTML > XLS > XLSX

        # 1. Try HTML (bs4) - Common for "Eleve.xls" exports from Ministry
        try:
            success = self.import_html(file_path, update_existing)
            if success:
                return
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'HTML parser skipped: {str(e)}'))

        # 2. Try Excel .xls (xlrd)
        try:
            success = self.import_excel_xls(file_path, update_existing)
            if success:
                return
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'XLS parser skipped: {str(e)}'))

        # 3. Try Excel .xlsx (openpyxl)
        try:
            success = self.import_excel_xlsx(file_path, update_existing)
            if success:
                return
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'XLSX parser skipped: {str(e)}'))

        self.stdout.write(self.style.ERROR('فشل استيراد الملف بجميع الطرق المتاحة. تأكد من أن الملف سليم ويحتوي على بيانات.'))

    def import_html(self, file_path, update_existing):
        content = ""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            return False

        if "<html" not in content.lower() and "<table" not in content.lower():
             return False

        soup = BeautifulSoup(content, 'html.parser')
        rows = soup.find_all('tr')

        return self.process_rows(rows, 'html', update_existing)

    def import_excel_xlsx(self, file_path, update_existing):
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        return self.process_rows(ws.iter_rows(values_only=True), 'xlsx', update_existing)

    def import_excel_xls(self, file_path, update_existing):
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

        return self.process_rows(rows, 'xls', update_existing)

    def process_rows(self, rows, mode, update_existing):
        to_create = []
        to_update = []
        processed_ids = set()
        existing_map = {s.student_id_number: s for s in Student.objects.all()}

        found_any = False
        error_count = 0

        for row in rows:
            sid = "Unknown"
            try:
                # Normalize row to list of strings
                if mode == 'html':
                    cells = row.find_all(['td', 'th'])
                    cols = [c.get_text(strip=True) for c in cells]
                else:
                    cols = [str(c).strip() if c is not None else '' for c in row]

                # Filter valid rows (Student ID must be digit)
                if not cols or len(cols) < 14: continue # Adjusted for flexibility

                sid = cols[0]
                if not sid.isdigit(): continue # Skip headers

                if sid in processed_ids: continue
                processed_ids.add(sid)
                found_any = True

                # Extract Data
                # Column mapping based on standard export format
                # 0: ID, 1: Last, 2: First, 3: Gender, 4: DOB, ..., 9: POB, 10: Level, 11: Class, 12: Sys, 13: EnrollNum, 14: EnrollDate

                dob = self.parse_date(cols[4])
                enroll_date = self.parse_date(cols[14]) if len(cols) > 14 else datetime.now().date()

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
                    # Placeholder data, to be filled later via Parents interface or updates
                    'guardian_name': '',
                    'mother_name': '',
                    'address': '',
                    'guardian_phone': ''
                }

                if sid in existing_map:
                    if update_existing:
                        student = existing_map[sid]
                        for key, value in student_data.items():
                            if key != 'student_id_number':
                                setattr(student, key, value)
                        to_update.append(student)
                else:
                    to_create.append(Student(**student_data))

            except Exception as e:
                # Log error but CONTINUE
                error_count += 1
                if error_count < 10: # Only print first 10 errors to avoid spam
                    print(f"Error processing row {sid}: {e}")
                continue

        # Bulk Operations
        if to_create:
            Student.objects.bulk_create(to_create)

        if to_update:
            Student.objects.bulk_update(to_update, [
                'last_name', 'first_name', 'gender', 'date_of_birth', 'place_of_birth',
                'academic_year', 'class_name', 'attendance_system', 'enrollment_number',
                'enrollment_date'
            ])

        if found_any:
            msg = f'Imported: {len(to_create)} New, {len(to_update)} Updated ({mode}). Errors: {error_count}'
            self.stdout.write(self.style.SUCCESS(msg))
            return True

        return False

    def parse_date(self, date_str):
        if not date_str or str(date_str).lower() in ['none', 'nan', '']:
             return datetime(1900, 1, 1).date()

        # Handle Excel Serial Date (e.g. 44567)
        if str(date_str).replace('.', '', 1).isdigit():
             try:
                 # Check if it's a serial date (approx > 10000)
                 val = float(date_str)
                 if val > 10000:
                     return datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(val) - 2).date()
             except: pass

        date_str = str(date_str).strip().split(' ')[0] # Remove time
        # Expanded formats including Dots
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y', '%Y.%m.%d'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return datetime(1900, 1, 1).date()
