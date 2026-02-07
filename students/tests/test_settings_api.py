from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from students.models import EmployeeProfile, SchoolSettings
import json

class SettingsAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.director_user = User.objects.create_user(username='director', password='password')
        EmployeeProfile.objects.create(user=self.director_user, role='director')
        self.settings = SchoolSettings.objects.create(
            name="Old Name",
            academic_year="2023",
            director_name="Old Dir",
            loan_limit=2
        )

    def test_partial_update_loan_limit(self):
        self.client.login(username='director', password='password')
        url = reverse('school_settings')

        data = {'loan_limit': 5}
        response = self.client.post(url, data, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.loan_limit, 5)
        self.assertEqual(self.settings.name, "Old Name") # Ensure other fields untouched

    def test_partial_update_school_info(self):
        self.client.login(username='director', password='password')
        url = reverse('school_settings')

        data = {'name': "New Name"}
        response = self.client.post(url, data, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.name, "New Name")
        self.assertEqual(self.settings.loan_limit, 2)
