from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomUser, Workspace, WorkspaceIntegration, WorkspaceMembership


class EnterpriseIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(username='integration-admin', email='integration@example.com', password='StrongPass123!', role='Admin')
        self.workspace = Workspace.objects.create(name='Integration newsroom', slug='integration-newsroom', owner=self.admin)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.admin, role='owner')
        self.client.force_authenticate(self.admin)

    @patch('users.api.requests.post')
    def test_integration_secret_is_redacted_and_provider_health_can_be_tested(self, post):
        post.return_value = Mock(status_code=204, raise_for_status=lambda: None)
        created = self.client.post(
            '/api/workspaces/integration-newsroom/integrations/',
            {'provider': 'slack', 'name': 'Editorial Slack', 'endpoint_url': 'https://hooks.example.com/slack', 'secret': 'do-not-return'},
            format='json',
        )
        self.assertEqual(created.status_code, 201)
        self.assertNotIn('do-not-return', str(created.data))
        tested = self.client.post(f"/api/workspaces/integration-newsroom/integrations/{created.data['id']}/", {}, format='json')
        self.assertEqual(tested.status_code, 200)
        self.assertEqual(tested.data['integration']['status'], 'healthy')
        self.assertTrue(WorkspaceIntegration.objects.filter(workspace=self.workspace, status='healthy').exists())

