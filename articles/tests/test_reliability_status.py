from django.test import TestCase
from rest_framework.test import APIClient

from articles.models import WorkspaceReliabilityPolicy
from users.models import CustomUser, Workspace, WorkspaceMembership


class ReliabilityStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(username='reliability-admin', email='reliability@example.com', password='StrongPass123!', role='Admin')
        self.workspace = Workspace.objects.create(name='Reliability newsroom', slug='reliability-newsroom', owner=self.admin)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.admin, role='owner')
        self.client.force_authenticate(self.admin)

    def test_reliability_objectives_can_be_configured(self):
        response = self.client.patch(
            '/articles/api/v2/operations/reliability/',
            {'rto_minutes': 60, 'rpo_minutes': 15, 'backup_region': 'eu-west-1', 'restore_verified_at': '2026-11-02T10:00:00Z'},
            format='json', HTTP_X_WORKSPACE_SLUG=self.workspace.slug,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['objectives']['rto_minutes'], 60)
        self.assertEqual(response.data['backup']['region'], 'eu-west-1')
        self.assertTrue(WorkspaceReliabilityPolicy.objects.filter(workspace=self.workspace, rpo_minutes=15).exists())

    def test_public_status_reports_service_state(self):
        self.client.force_authenticate(None)
        response = self.client.get('/status/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.data['status'], {'operational', 'degraded'})
        self.assertIn('database', response.data['services'])

    def test_public_status_page_is_available_without_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.get('/articles/status-page/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Article Studio status')
        self.assertContains(response, 'status-page.js')
