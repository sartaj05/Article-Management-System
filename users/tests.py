from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomUser, Profile, SecurityEvent


class UserFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='profile-test', email='profile-test@example.com',
            password='StrongPass123!', role='Journalist',
        )
        self.client.force_authenticate(user=self.user)

    def test_profile_get_and_update(self):
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

        response = self.client.patch(
            '/api/profile/', {'first_name': 'Updated', 'bio': 'Writer profile'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(response.data['bio'], 'Writer profile')

    def test_public_registration_cannot_select_admin_role(self):
        self.client.force_authenticate(user=None)
        response = self.client.post('/api/register/', {
            'first_name': 'New', 'last_name': 'Writer', 'username': 'new-writer',
            'email': 'new-writer@example.com', 'password': 'StrongPass123!',
            'role': 'Admin', 'checkbox': True,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_failed_login_attempts_are_throttled_and_recorded(self):
        self.client.force_authenticate(user=None)
        for _ in range(5):
            response = self.client.post('/api/login/', {'username': 'profile-test', 'password': 'wrong-password'}, format='json')
            self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/login/', {'username': 'profile-test', 'password': 'wrong-password'}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(SecurityEvent.objects.filter(username='profile-test', event_type='login_failed').count(), 5)
