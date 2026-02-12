from django.test import TestCase
from students.models import Student
from students.resources import StudentResource
from tablib import Dataset
from datetime import date
from students.import_utils import parse_date

class ImportLogicTest(TestCase):
    def test_parse_date(self):
        self.assertEqual(parse_date("2023-01-01"), date(2023, 1, 1))
        self.assertEqual(parse_date("01/01/2023"), date(2023, 1, 1))
        self.assertEqual(parse_date("01-01-2023"), date(2023, 1, 1))
        self.assertEqual(parse_date("2023.01.01"), date(2023, 1, 1))
        self.assertEqual(parse_date("44927"), date(2023, 1, 1)) # Excel serial date approx

    def test_student_resource_import(self):
        # Create dataset
        headers = ['student_id_number', 'last_name', 'first_name', 'gender', 'date_of_birth',
                   'place_of_birth', 'academic_year', 'class_name', 'attendance_system',
                   'enrollment_number', 'enrollment_date']
        data = [
            ('12345', 'Doe', 'John', 'M', date(2010, 1, 1), 'City', 'Level 1', 'Class A', 'Full', 'EN123', date(2023, 9, 1)),
            ('67890', 'Smith', 'Jane', 'F', date(2011, 2, 2), 'Town', 'Level 2', 'Class B', 'Half', 'EN456', date(2023, 9, 1))
        ]
        dataset = Dataset(*data, headers=headers)

        resource = StudentResource()
        result = resource.import_data(dataset, dry_run=False)

        self.assertFalse(result.has_errors())
        self.assertEqual(Student.objects.count(), 2)

        s1 = Student.objects.get(student_id_number='12345')
        self.assertEqual(s1.last_name, 'Doe')

        # Test Update
        data_update = [
            ('12345', 'Doe Updated', 'John', 'M', date(2010, 1, 1), 'City', 'Level 1', 'Class A', 'Full', 'EN123', date(2023, 9, 1))
        ]
        dataset_update = Dataset(*data_update, headers=headers)
        result_update = resource.import_data(dataset_update, dry_run=False)

        self.assertFalse(result_update.has_errors())
        s1.refresh_from_db()
        self.assertEqual(s1.last_name, 'Doe Updated')
