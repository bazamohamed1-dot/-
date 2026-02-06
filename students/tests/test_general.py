from django.test import TestCase
from rest_framework.test import APIClient
from students.models import Student, LibraryLoan
from datetime import date, timedelta

class LibraryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = Student.objects.create(
            student_id_number='1234567890123456',
            last_name='Test',
            first_name='Student',
            gender='Male',
            date_of_birth='2010-01-01',
            place_of_birth='City',
            academic_year='1',
            class_name='1',
            attendance_system='Half-Board',
            enrollment_date='2020-01-01',
            guardian_name='G',
            mother_name='M',
            address='Addr',
            guardian_phone='0000000000'
        )

    def test_library_flow(self):
        # 1. Scan Card
        resp = self.client.post('/canteen/library/scan/', {'barcode': '1234567890123456'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['student']['id'], self.student.id)

        # 2. Loan Book
        resp = self.client.post('/canteen/library/loan/', {'student_id': self.student.id, 'book_title': 'Python 101'}, format='json')
        self.assertEqual(resp.status_code, 201)
        loan_id = resp.data['id']

        # Verify Loan exists
        loan = LibraryLoan.objects.get(id=loan_id)
        self.assertEqual(loan.book_title, 'Python 101')
        self.assertEqual(loan.expected_return_date, date.today() + timedelta(days=15))

        # 3. Stats
        resp = self.client.get('/canteen/library/stats/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['borrowers_count'], 1)

        # 4. Return Book
        resp = self.client.post('/canteen/library/return/', {'loan_id': loan_id}, format='json')
        self.assertEqual(resp.status_code, 200)

        loan.refresh_from_db()
        self.assertTrue(loan.is_returned)
        self.assertEqual(loan.actual_return_date, date.today())
