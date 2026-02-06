from django.test import TestCase
from django.contrib.auth.models import User
from students.models import EmployeeProfile
from rest_framework.test import APIClient
from django.urls import reverse

class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.director_user = User.objects.create_user(username='director', password='password123')
        self.director_profile = EmployeeProfile.objects.create(user=self.director_user, role='director')

        self.store_user = User.objects.create_user(username='store', password='password123')
        self.store_profile = EmployeeProfile.objects.create(user=self.store_user, role='storekeeper')

    def test_login_success(self):
        resp = self.client.post('/canteen/auth/login/', {'username': 'director', 'password': 'password123'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertEqual(resp.data['role'], 'director')

        # Check token stored
        self.director_profile.refresh_from_db()
        self.assertEqual(resp.data['token'], self.director_profile.current_session_token)

    def test_failed_login_lock(self):
        url = '/canteen/auth/login/'
        # 1st fail
        resp = self.client.post(url, {'username': 'store', 'password': 'wrong'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.store_profile.refresh_from_db()
        self.assertEqual(self.store_profile.failed_login_attempts, 1)

        # 2nd fail
        resp = self.client.post(url, {'username': 'store', 'password': 'wrong'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.store_profile.refresh_from_db()
        self.assertEqual(self.store_profile.failed_login_attempts, 2)

        # 3rd fail -> Lock
        resp = self.client.post(url, {'username': 'store', 'password': 'wrong'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.store_profile.refresh_from_db()
        self.assertTrue(self.store_profile.is_locked)

        # 4th attempt (should be locked)
        resp = self.client.post(url, {'username': 'store', 'password': 'password123'}, format='json') # Correct pass
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data['code'], 'LOCKED')

    def test_session_verify(self):
        # Login
        resp = self.client.post('/canteen/auth/login/', {'username': 'director', 'password': 'password123'}, format='json')
        token = resp.data['token']

        # Verify
        # self.client.force_authenticate(user=self.director_user)
        resp = self.client.post('/canteen/auth/verify/', {'token': token}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['valid'])

        # Wrong token
        resp = self.client.post('/canteen/auth/verify/', {'token': 'wrong'}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_admin_unlock_reset(self):
        # Lock store user
        self.store_profile.is_locked = True
        self.store_profile.save()

        # Login Director
        self.client.force_authenticate(user=self.director_user)

        # Unlock
        resp = self.client.post(f'/canteen/api/users/{self.store_user.id}/unlock_account/', format='json')
        self.assertEqual(resp.status_code, 200)

        self.store_profile.refresh_from_db()
        self.assertFalse(self.store_profile.is_locked)
        self.assertEqual(self.store_profile.failed_login_attempts, 0)

        # Reset Session
        self.store_profile.current_session_token = 'sometoken'
        self.store_profile.save()

        resp = self.client.post(f'/canteen/api/users/{self.store_user.id}/reset_session/', format='json')
        self.assertEqual(resp.status_code, 200)

        self.store_profile.refresh_from_db()
        self.assertIsNone(self.store_profile.current_session_token)
