from rest_framework.test import APITestCase

from articles.models import AuditLog
from .models import CustomUser


class PlatformAuditEventTests(APITestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='platform-audit-admin', email='platform-audit@example.com',
            password='StrongPass123!', role='Admin',
        )
        self.client.force_authenticate(self.admin)

    def test_workspace_and_integration_changes_are_audited_without_secrets(self):
        workspace_response = self.client.post('/api/workspaces/', {'name': 'Audit Workspace'}, format='json')
        self.assertEqual(workspace_response.status_code, 201)
        workspace = workspace_response.data
        self.assertTrue(AuditLog.objects.filter(action='workspace_created', target_id=workspace['id']).exists())

        integration_response = self.client.post(
            f"/api/workspaces/{workspace['slug']}/integrations/",
            {'provider': 'slack', 'name': 'Audit Slack', 'endpoint_url': 'https://example.com/hook', 'secret': 'do-not-log'},
            format='json',
        )
        self.assertEqual(integration_response.status_code, 201)
        event = AuditLog.objects.get(action='integration_created', target_id=integration_response.data['id'])
        self.assertNotIn('do-not-log', str(event.details))

    def test_privacy_export_and_api_key_lifecycle_are_audited(self):
        export = self.client.post('/api/privacy/export/', {}, format='json')
        self.assertEqual(export.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action='privacy_export_requested').exists())

        key = self.client.post('/api/developer/keys/', {'name': 'Audit key', 'scopes': ['articles:read']}, format='json')
        self.assertEqual(key.status_code, 201)
        key_id = key.data['details']['id']
        self.assertTrue(AuditLog.objects.filter(action='api_key_created', target_id=key_id).exists())
        self.client.post(f'/api/developer/keys/{key_id}/', {}, format='json')
        self.assertTrue(AuditLog.objects.filter(action='api_key_rotated', target_id=key_id).exists())
        self.client.delete(f'/api/developer/keys/{key_id}/')
        self.assertTrue(AuditLog.objects.filter(action='api_key_revoked', target_id=key_id).exists())
