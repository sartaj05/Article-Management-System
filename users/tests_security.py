from datetime import timedelta
from hashlib import sha256

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.api import resolve_public_api_key
from users.models import CustomUser, PublicAPIKey, WebhookEndpoint


class SecurityHardeningTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='security-owner', email='security@example.com', password='StrongPass123!', role='Editor')
        self.client.force_authenticate(self.user)

    def test_api_key_defaults_to_expiration_and_expired_keys_are_rejected(self):
        response = self.client.post('/developer/keys/', {'name': 'Demo feed', 'scopes': ['articles:read']}, format='json')
        self.assertEqual(response.status_code, 201)
        key = PublicAPIKey.objects.get(owner=self.user)
        self.assertIsNotNone(key.expires_at)
        self.assertEqual(resolve_public_api_key(response.data['key'], 'articles:read'), self.user)
        key.expires_at = timezone.now() - timedelta(minutes=1)
        key.save(update_fields=['expires_at'])
        self.assertIsNone(resolve_public_api_key(response.data['key'], 'articles:read'))

    def test_api_key_rotation_and_webhook_secret_rotation_return_new_secrets(self):
        raw = 'as_original-secret'
        key = PublicAPIKey.objects.create(owner=self.user, name='Rotate me', prefix=raw[:10], key_hash=sha256(raw.encode()).hexdigest())
        rotated = self.client.post(f'/developer/keys/{key.id}/', {}, format='json')
        self.assertEqual(rotated.status_code, 200)
        self.assertNotEqual(rotated.data['key'], raw)
        self.assertIsNone(resolve_public_api_key(raw))
        endpoint = WebhookEndpoint.objects.create(owner=self.user, url='https://example.com/hooks', secret='old-secret')
        response = self.client.post(f'/developer/webhooks/{endpoint.id}/rotate-secret/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data['secret'], 'old-secret')
