from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser, PublicAPIKeyUsage


class APIUsageTests(TestCase):
    def test_public_api_usage_is_visible_only_to_key_owner(self):
        user = CustomUser.objects.create_user(username='api-owner', email='api-owner@example.com', password='StrongPass123!', role='Editor')
        client = APIClient()
        client.force_authenticate(user)
        created = client.post('/developer/keys/', {'name': 'Usage key', 'scopes': ['articles:read']}, format='json')
        raw_key = created.data['key']
        client.get('/articles/api/v2/public/articles/', HTTP_X_API_KEY=raw_key)
        key_id = created.data['details']['id']
        response = client.get(f'/developer/keys/{key_id}/usage/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['request_count'], 1)
        self.assertEqual(PublicAPIKeyUsage.objects.count(), 1)
