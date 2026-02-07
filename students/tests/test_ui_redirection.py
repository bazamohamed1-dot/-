from django.test import TestCase, Client
from django.contrib.auth.models import User
from students.models import EmployeeProfile, Student, CanteenAttendance
from django.urls import reverse

class DashboardRedirectionTest(TestCase):
    def setUp(self):
        self.client = Client()

        # Create users
        self.director_user = User.objects.create_user(username='director', password='password')
        EmployeeProfile.objects.create(user=self.director_user, role='director')

        self.librarian_user = User.objects.create_user(username='librarian', password='password')
        EmployeeProfile.objects.create(user=self.librarian_user, role='librarian')

        self.storekeeper_user = User.objects.create_user(username='storekeeper', password='password')
        EmployeeProfile.objects.create(user=self.storekeeper_user, role='storekeeper')

    def test_director_access_dashboard(self):
        self.client.login(username='director', password='password')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'students/dashboard.html')

    def test_librarian_redirect(self):
        self.client.login(username='librarian', password='password')
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('library_home'))

    def test_storekeeper_redirect(self):
        self.client.login(username='storekeeper', password='password')
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('canteen_home'))

    def test_unauthenticated_access(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('landing'))
