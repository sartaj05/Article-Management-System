from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomUser, PrivacyConsent, PrivacyRequest


class PrivacyFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='privacy-user', email='privacy@example.com', password='StrongPass123!', role='Journalist',
        )
        self.client.force_authenticate(self.user)

    def test_user_can_update_preferences_and_export_data(self):
        response = self.client.patch('/api/privacy/preferences/', {
            'analytics_enabled': True, 'marketing_enabled': False,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PrivacyConsent.objects.filter(user=self.user, purpose='analytics', granted=True).exists())

        response = self.client.post('/api/privacy/export/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'completed')
        self.assertTrue(PrivacyRequest.objects.filter(user=self.user, request_type='export').exists())

    def test_deletion_requires_explicit_confirmation(self):
        response = self.client.post('/api/privacy/delete/', {'confirmation': 'delete'}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/privacy/delete/', {'confirmation': 'DELETE'}, format='json')
        self.assertEqual(response.status_code, 202)
        self.assertTrue(PrivacyRequest.objects.filter(user=self.user, request_type='deletion').exists())
