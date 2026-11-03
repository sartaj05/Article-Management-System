from django.test import TestCase
from rest_framework.test import APIClient

from articles.audit import record_audit_event
from articles.models import AuditLog
from users.models import CustomUser, Workspace, WorkspaceMembership


class ComplianceGovernanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(
            username='compliance-admin', email='compliance@example.com',
            password='StrongPass123!', role='Admin',
        )
        self.workspace = Workspace.objects.create(name='Compliance newsroom', slug='compliance-newsroom', owner=self.admin)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.admin, role='owner')
        self.client.force_authenticate(self.admin)

    def test_audit_events_form_a_verifiable_hash_chain(self):
        record_audit_event(actor=self.admin, workspace=self.workspace, action='first_event', target_model='Workspace', target_id=self.workspace.id)
        record_audit_event(actor=self.admin, workspace=self.workspace, action='second_event', target_model='Workspace', target_id=self.workspace.id)
        entries = list(AuditLog.objects.filter(workspace=self.workspace).order_by('created_at', 'id'))
        self.assertEqual(entries[1].previous_hash, entries[0].event_hash)
        response = self.client.get('/articles/api/v2/compliance/evidence/', HTTP_X_WORKSPACE_SLUG=self.workspace.slug)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['audit_chain']['verified'])

    def test_legal_hold_can_be_created_and_released(self):
        created = self.client.post(
            '/articles/api/v2/compliance/legal-holds/',
            {'name': 'Investigation 2026-01', 'reason': 'Preserve newsroom records.'},
            format='json', HTTP_X_WORKSPACE_SLUG=self.workspace.slug,
        )
        self.assertEqual(created.status_code, 201)
        released = self.client.patch(
            f"/articles/api/v2/compliance/legal-holds/{created.data['id']}/",
            {'is_active': False}, format='json', HTTP_X_WORKSPACE_SLUG=self.workspace.slug,
        )
        self.assertEqual(released.status_code, 200)
        self.assertFalse(released.data['is_active'])

    def test_compliance_center_renders_governance_sections(self):
        self.client.force_login(self.admin)
        response = self.client.get('/articles/workspace/compliance/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Compliance &amp; audit center')
        self.assertContains(response, 'Create legal hold')
