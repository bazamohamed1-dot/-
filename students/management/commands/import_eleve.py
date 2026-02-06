from django.core.management.base import BaseCommand
from students.models import Student
from bs4 import BeautifulSoup
import openpyxl
import os
from datetime import datetime

class Command(BaseCommand):
    help = 'Imports students from Eleve.xls (HTML format) or standard Excel .xlsx with bulk operations.'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Path to the file to import', required=False)
        parser.add_argument('--update-existing', action='store_true', help='Update existing students if found')

    def handle(self, *args, **options):
        file_path = options.get('file') or 'Eleve.xls'
        update_existing = options.get('update_existing', False)

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File {file_path} not found'))
            return

        # Fetch existing students map: student_id_number -> pk
        self.existing_map = {s.student_id_number: s.pk for s in Student.objects.all()}
        self.to_create = []
        self.to_update = []
        self.processed_ids_in_file = set()

        # Try HTML (bs4) first
        html_success = False
        try:
            success = self.import_html(file_path)
            if success:
                self.process_batches(update_existing, mode="HTML")
                html_success = True
            else:
                self.stdout.write(self.style.WARNING('HTML parser found 0 records. Attempting Excel parser...'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'HTML parsing failed or file is not HTML ({str(e)}). Attempting Excel parser...'))

        if html_success:
            return

        # Try Excel (openpyxl)
        # Reset lists if HTML failed partially (though usually it fails before adding anything if format is wrong)
        self.to_create = []
        self.to_update = []
        self.processed_ids_in_file = set()

        try:
            success = self.import_excel(file_path)
            if success:
                self.process_batches(update_existing, mode="Excel")
            else:
                self.stdout.write(self.style.ERROR('Excel parser found 0 records.'))
        except Exception as e:
            raise Exception(f'All import methods failed. Ensure file is Eleve.xls (HTML) or .xlsx. Details: {str(e)}')

    def process_batches(self, update_existing, mode):
        created_count = 0
        updated_count = 0

        if self.to_create:
            Student.objects.bulk_create(self.to_create)
            created_count = len(self.to_create)

        if update_existing and self.to_update:
            # Fields to update
            fields = ['last_name', 'first_name', 'gender', 'date_of_birth', 'place_of_birth',
                      'academic_year', 'class_name', 'attendance_system', 'enrollment_number',
                      'enrollment_date']
            Student.objects.bulk_update(self.to_update, fields)
            updated_count = len(self.to_update)

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {created_count} new students and updated {updated_count} existing ({mode} Mode).'))


    def import_html(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except UnicodeDecodeError:
            raise ValueError("File is binary or not UTF-8")

        if "<html" not in content.lower() and "<table" not in content.lower():
             raise ValueError("Content does not look like HTML")

        soup = BeautifulSoup(content, 'html.parser')
        rows = soup.find_all('tr')

        found_any = False
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all('td')]
            if not cols or len(cols) < 15:
                continue

            self.parse_and_prepare(cols)
            found_any = True

        return found_any

    def import_excel(self, file_path):
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active

        found_any = False
        for row in ws.iter_rows(values_only=True):
            cols = [str(c).strip() if c is not None else '' for c in row]
            if not cols or len(cols) < 15:
                continue
            if not cols[0].isdigit():
                continue

            self.parse_and_prepare(cols)
            found_any = True

        return found_any

    def parse_and_prepare(self, cols):
        student_id = cols[0]
        if not student_id or not student_id.isdigit():
            return

        if student_id in self.processed_ids_in_file:
            return
        self.processed_ids_in_file.add(student_id)

        last_name = cols[1]
        first_name = cols[2]
        if not last_name or not first_name:
            return

        gender = cols[3]
        dob_str = cols[4]
        pob = cols[9]
        level = cols[10]
        class_num = cols[11]
        full_class = f"{level} {class_num}".strip()
        system = cols[12]
        enroll_num = cols[13]
        enroll_date_str = cols[14]

        dob = self.parse_date(dob_str)
        enroll_date = self.parse_date(enroll_date_str)

        student_data = Student(
            student_id_number=student_id,
            last_name=last_name,
            first_name=first_name,
            gender=gender,
            date_of_birth=dob,
            place_of_birth=pob,
            academic_year=level,
            class_name=full_class,
            attendance_system=system,
            enrollment_number=enroll_num,
            enrollment_date=enroll_date if enroll_date else datetime.now().date(),
            guardian_name='غير متوفر',
            mother_name='غير متوفر',
            address='غير متوفر',
            guardian_phone='0000000000'
        )

        if student_id in self.existing_map:
            # Existing: prepare for update
            student_data.pk = self.existing_map[student_id]
            self.to_update.append(student_data)
        else:
            # New: prepare for create
            self.to_create.append(student_data)

    def parse_date(self, date_str):
        if not date_str: return None
        try:
            d_part = date_str.split(' ')[0]
            return datetime.strptime(d_part, '%Y-%m-%d').date()
        except:
            return None
