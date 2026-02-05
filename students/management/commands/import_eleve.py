from django.core.management.base import BaseCommand
from students.models import Student
from bs4 import BeautifulSoup
import openpyxl
import os
from datetime import datetime

class Command(BaseCommand):
    help = 'Imports students from Eleve.xls (HTML format) or standard Excel .xlsx'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Path to the file to import', required=False)

    def handle(self, *args, **options):
        file_path = options.get('file') or 'Eleve.xls'

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File {file_path} not found'))
            return

        # Try HTML (bs4) first
        html_success = False
        try:
            count, updated = self.import_html(file_path)
            if count > 0 or updated > 0:
                self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} new students and updated {updated} existing (HTML Mode).'))
                html_success = True
            else:
                self.stdout.write(self.style.WARNING('HTML parser found 0 records. Attempting Excel parser...'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'HTML parsing failed or file is not HTML ({str(e)}). Attempting Excel parser...'))

        if html_success:
            return

        # Try Excel (openpyxl)
        try:
            count, updated = self.import_excel(file_path)
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} new students and updated {updated} existing (Excel Mode).'))
        except Exception as e:
            # Raise exception so the UI view catches it and displays as error
            raise Exception(f'All import methods failed. Ensure file is Eleve.xls (HTML) or .xlsx. Details: {str(e)}')

    def import_html(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except UnicodeDecodeError:
            # If utf-8 fails, it might be binary (Excel)
            raise ValueError("File is binary or not UTF-8")

        if "<html" not in content.lower() and "<table" not in content.lower():
             raise ValueError("Content does not look like HTML")

        soup = BeautifulSoup(content, 'html.parser')
        rows = soup.find_all('tr')

        count = 0
        updated = 0
        processed_ids = set()

        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all('td')]
            if not cols or len(cols) < 15:
                continue

            res = self.save_student(cols, processed_ids)
            if res == 'created': count += 1
            elif res == 'updated': updated += 1

        return count, updated

    def import_excel(self, file_path):
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active

        count = 0
        updated = 0
        processed_ids = set()

        for row in ws.iter_rows(values_only=True):
            # Convert row to list of strings/None
            cols = [str(c).strip() if c is not None else '' for c in row]

            # Skip header or empty
            if not cols or len(cols) < 15:
                continue

            # Check if first col is digit (ID)
            if not cols[0].isdigit():
                continue

            res = self.save_student(cols, processed_ids)
            if res == 'created': count += 1
            elif res == 'updated': updated += 1

        return count, updated

    def save_student(self, cols, processed_ids):
        # Mapping based on HTML structure
        # 0: ID, 1: Last, 2: First, 3: Gender, 4: DOB, 9: POB, 10: Level, 11: Class, 12: System, 13: EnrollNum, 14: EnrollDate

        student_id = cols[0]

        # Validation
        if not student_id or not student_id.isdigit():
            return None

        if student_id in processed_ids:
            return None
        processed_ids.add(student_id)

        last_name = cols[1]
        first_name = cols[2]

        if not last_name or not first_name:
            return None

        gender = cols[3]
        dob_str = cols[4]
        pob = cols[9]
        level = cols[10]
        class_num = cols[11]
        full_class = f"{level} {class_num}".strip()
        system = cols[12]
        enroll_num = cols[13]
        enroll_date_str = cols[14]

        # Parse dates
        dob = self.parse_date(dob_str)
        enroll_date = self.parse_date(enroll_date_str)

        defaults = {
            'last_name': last_name,
            'first_name': first_name,
            'gender': gender,
            'date_of_birth': dob,
            'place_of_birth': pob,
            'academic_year': level,
            'class_name': full_class,
            'attendance_system': system,
            'enrollment_number': enroll_num,
            'enrollment_date': enroll_date if enroll_date else datetime.now().date(),
            'guardian_name': 'غير متوفر',
            'mother_name': 'غير متوفر',
            'address': 'غير متوفر',
            'guardian_phone': '0000000000',
        }

        obj, created = Student.objects.update_or_create(
            student_id_number=student_id,
            defaults=defaults
        )

        return 'created' if created else 'updated'

    def parse_date(self, date_str):
        if not date_str: return None
        # Handle formats: YYYY-MM-DD (standard) or others if needed
        # Openpyxl might return 'YYYY-MM-DD HH:MM:SS' string or datetime object (handled by str() above)
        # But we cast to str in import_excel.
        # If openpyxl returned datetime, str() makes it 'YYYY-MM-DD HH:MM:SS'.

        try:
            # First try split by space (remove time)
            d_part = date_str.split(' ')[0]
            return datetime.strptime(d_part, '%Y-%m-%d').date()
        except:
            return None
