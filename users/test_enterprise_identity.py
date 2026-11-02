from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomUser, SSOProvider, Workspace, WorkspaceMembership


class EnterpriseIdentityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(username='identity-admin', email='identity-admin@example.com', password='StrongPass123!', role='Admin')
        self.workspace = Workspace.objects.create(name='Identity newsroom', slug='identity-newsroom', owner=self.admin)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.admin, role='owner')

    @patch('users.api.requests.get')
    @patch('users.api.requests.post')
    def test_oidc_callback_exchanges_code_and_provisions_user(self, post, get):
        SSOProvider.objects.create(
            provider='google', client_id='client-id', client_secret='client-secret',
            discovery_url='https://idp.example.com/authorize', token_url='https://idp.example.com/token',
            userinfo_url='https://idp.example.com/userinfo', is_enabled=True,
        )
        start = self.client.get('/api/sso/google/start/')
        self.assertEqual(start.status_code, 200)
        state = start.data['state']
        post.return_value = Mock(ok=True, json=lambda: {'access_token': 'access-token'})
        get.return_value = Mock(ok=True, json=lambda: {'email': 'new.user@example.com', 'given_name': 'New', 'family_name': 'User'})
        response = self.client.get(f'/api/sso/google/callback/?state={state}&code=auth-code')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['authenticated'])
        self.assertTrue(CustomUser.objects.filter(email='new.user@example.com').exists())

    def test_scim_token_can_provision_and_deactivate_workspace_user(self):
        self.client.force_authenticate(self.admin)
        token_response = self.client.post('/api/workspaces/identity-newsroom/scim/tokens/')
        self.assertEqual(token_response.status_code, 201)
        raw_token = token_response.data['token']
        self.client.force_authenticate(None)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {raw_token}'}
        created = self.client.post('/api/scim/v2/identity-newsroom/Users/', {
            'userName': 'scim.user@example.com', 'active': True, 'role': 'editor',
        }, format='json', **headers)
        self.assertEqual(created.status_code, 201)
        user_id = created.data['id']
        self.assertTrue(CustomUser.objects.filter(email='scim.user@example.com', is_active=True).exists())
        disabled = self.client.patch(f'/api/scim/v2/identity-newsroom/Users/{user_id}/', {'active': False}, format='json', **headers)
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(CustomUser.objects.get(pk=user_id).is_active)
