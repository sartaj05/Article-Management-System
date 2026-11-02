from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomUser, Workspace, WorkspaceIntegration, WorkspaceMembership
from .integration_secrets import decrypt_integration_secret


class IntegrationSecretTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='secret-admin', email='secret@example.com', password='StrongPass123!', role='Admin')
        self.workspace = Workspace.objects.create(name='Secrets Newsroom', slug='secrets-newsroom', owner=self.user)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role='owner')
        self.client.force_authenticate(self.user)

    def test_secret_is_encrypted_and_never_returned(self):
        response = self.client.post(f'/api/workspaces/{self.workspace.slug}/integrations/', {
            'provider': 'slack', 'name': 'Alerts', 'endpoint_url': 'https://hooks.example.test', 'secret': 'super-secret-token',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['secret_configured'])
        self.assertNotIn('secret', response.data)
        integration = WorkspaceIntegration.objects.get(pk=response.data['id'])
        self.assertNotEqual(integration.encrypted_secret, 'super-secret-token')
        self.assertEqual(integration.secret, '')
        self.assertEqual(decrypt_integration_secret(integration.encrypted_secret), 'super-secret-token')

    @patch('users.api.requests.post')
    def test_health_check_uses_decrypted_secret(self, post):
        post.return_value.ok = True
        post.return_value.status_code = 204
        integration = WorkspaceIntegration.objects.create(
            workspace=self.workspace, provider='slack', name='Health', endpoint_url='https://hooks.example.test',
            encrypted_secret=__import__('users.integration_secrets', fromlist=['encrypt_integration_secret']).encrypt_integration_secret('health-token'),
            created_by=self.user,
        )
        response = self.client.post(f'/api/workspaces/{self.workspace.slug}/integrations/{integration.id}/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer health-token')
