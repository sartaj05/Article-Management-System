from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from articles.models import AuditLog
from .models import CustomUser, Workspace, WorkspaceMembership


class WorkspaceDataResidencyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(username='residency-admin', email='residency@example.com', password='StrongPass123!', role='Admin')
        self.workspace = Workspace.objects.create(name='EU Newsroom', slug='eu-newsroom', owner=self.admin)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.admin, role='owner')
        self.client.force_authenticate(self.admin)

    def test_workspace_admin_can_set_region_and_retention(self):
        response = self.client.patch(f'/api/workspaces/{self.workspace.slug}/controls/', {'data_region': 'eu', 'retention_days': 730}, format='json')
        self.assertEqual(response.status_code, 200)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.data_region, 'eu')
        self.assertEqual(self.workspace.retention_days, 730)

    def test_retention_command_uses_workspace_policy(self):
        old = AuditLog.objects.create(workspace=self.workspace, actor=self.admin, action='old-event')
        AuditLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=800))
        call_command('apply_data_retention')
        self.assertFalse(AuditLog.objects.filter(pk=old.pk).exists())
