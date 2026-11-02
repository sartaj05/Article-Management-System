from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomUser, SupportTicket, Workspace, WorkspaceMembership


class SupportOperationsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(username='support-admin', email='support-admin@example.com', password='StrongPass123!', role='Admin')
        self.workspace = Workspace.objects.create(name='Support newsroom', slug='support-newsroom', owner=self.admin)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.admin, role='owner')
        self.client.force_authenticate(self.admin)

    def test_ticket_has_priority_sla_and_threaded_admin_resolution(self):
        created = self.client.post(
            '/api/support/tickets/',
            {'workspace_slug': self.workspace.slug, 'subject': 'Import is delayed', 'description': 'The import queue is waiting.', 'priority': 'urgent'},
            format='json',
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['priority'], 'urgent')
        self.assertEqual(len(created.data['messages']), 1)
        updated = self.client.patch(
            f"/api/support/tickets/{created.data['id']}/",
            {'status': 'resolved', 'message': 'The queue is healthy now.'}, format='json',
            HTTP_X_WORKSPACE_SLUG=self.workspace.slug,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data['status'], 'resolved')
        self.assertEqual(len(updated.data['messages']), 2)
        self.assertTrue(SupportTicket.objects.get(pk=created.data['id']).resolved_at)
