from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .models import AuthenticationPolicy, CustomUser, SSOProvider, TwoFactorAuth


class AuthenticationPolicyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(username='auth-policy-admin', email='auth-policy@example.com', password='StrongPass123!', role='Admin')
        self.client.force_authenticate(self.admin)

    def test_admin_can_require_mfa_and_bound_session_lifetime(self):
        response = self.client.patch('/api/security/authentication-policy/', {'require_mfa': True, 'max_session_minutes': 30}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AuthenticationPolicy.objects.get(name='default').require_mfa)
        self.client.force_authenticate(None)
        blocked = self.client.post('/api/login/', {'username': self.admin.username, 'password': 'StrongPass123!'})
        self.assertEqual(blocked.status_code, 403)

    @patch('users.saml.validate_saml_response')
    def test_saml_callback_uses_signed_assertion_adapter(self, validate):
        provider = SSOProvider.objects.create(provider='saml', client_id='sp-id', metadata_url='https://idp.example/metadata', is_enabled=True)
        start = self.client.get('/api/sso/saml/start/')
        self.assertEqual(start.status_code, 200)
        validate.return_value = {'email': 'saml-user@example.com'}
        response = self.client.get(f"/api/sso/saml/callback/?state={start.data['state']}&SAMLResponse=signed-response")
        self.assertEqual(response.status_code, 200)
