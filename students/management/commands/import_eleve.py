from django.core.management.base import BaseCommand
from students.models import Student
from bs4 import BeautifulSoup
import os
from datetime import datetime

class Command(BaseCommand):
    help = 'Imports students from Eleve.xls (HTML format)'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Path to the file to import', required=False)

    def handle(self, *args, **options):
        file_path = options.get('file') or 'Eleve.xls'

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File {file_path} not found'))
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        soup = BeautifulSoup(content, 'html.parser')
        rows = soup.find_all('tr')

        count = 0
        updated = 0
        processed_ids = set()

        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all('td')]
            if not cols or len(cols) < 15:
                continue

            # Map fields
            student_id = cols[0].strip()

            # Validation: Skip empty or non-numeric IDs
            if not student_id or not student_id.isdigit():
                continue

            # Avoid duplicates within the file (handle nested rows issue)
            if student_id in processed_ids:
                continue
            processed_ids.add(student_id)

            last_name = cols[1].strip()
            first_name = cols[2].strip()

            # Validation: Skip entries with empty names
            if not last_name or not first_name:
                continue
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
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except:
                dob = None

            try:
                enroll_date = datetime.strptime(enroll_date_str, '%Y-%m-%d').date()
            except:
                enroll_date = None

            # Create or Update
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

            if created:
                count += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} new students and updated {updated} existing.'))
