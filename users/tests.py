from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomUser, NewsletterSubscription, Profile, ReaderInterest, SecurityEvent


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

    def test_newsletter_subscription_can_be_created_and_disabled(self):
        self.client.force_authenticate(user=None)
        response = self.client.post('/api/newsletter/subscribe/', {'email': 'reader@example.com', 'frequency': 'weekly'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(NewsletterSubscription.objects.get(email='reader@example.com').is_active)
        response = self.client.delete('/api/newsletter/subscribe/?email=reader@example.com')
        self.assertTrue(response.data['unsubscribed'])

    def test_reader_interests_can_be_followed(self):
        response = self.client.post('/api/reader/interests/', {'interest_type': 'category', 'value': 'news'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(ReaderInterest.objects.filter(user=self.user, value='news').exists())
        self.assertEqual(self.client.get('/api/reader/interests/').status_code, 200)
