from rest_framework.test import APITestCase

from articles.models import AuditLog
from users.models import CustomUser, Workspace, WorkspaceMembership


class AdminAuditCoverageTests(APITestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin-audit-coverage', email='admin-audit-coverage@example.com',
            password='StrongPass123!', role='Admin',
        )
        self.workspace = Workspace.objects.create(name='Admin Audit Desk', slug='admin-audit-desk', owner=self.admin)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.admin, role='owner')
        self.client.force_authenticate(self.admin)

    def test_support_and_administration_mutations_are_audited(self):
        support = self.client.post(
            '/api/support/tickets/',
            {'workspace_slug': self.workspace.slug, 'subject': 'Audit test', 'description': 'A test support request.', 'priority': 'high'},
            format='json',
        )
        self.assertEqual(support.status_code, 201)
        self.client.patch(
            f"/api/support/tickets/{support.data['id']}/",
            {'workspace_slug': self.workspace.slug, 'status': 'resolved'}, format='json',
        )
        self.client.post('/api/feature-flags/', {'key': 'audit-ui', 'description': 'Audit UI', 'is_enabled': True, 'rollout_percent': 50}, format='json')
        self.client.patch('/api/role-capabilities/', {'role': 'Editor', 'capability': 'article.publish', 'enabled': False}, format='json')
        expected = {'support_ticket_created', 'support_ticket_updated', 'feature_flag_updated', 'role_capability_updated'}
        self.assertTrue(expected.issubset(set(AuditLog.objects.values_list('action', flat=True))))

    def test_category_and_tag_changes_are_audited(self):
        category = self.client.post('/articles/api/v2/categories/', {'name': 'Audit category', 'description': 'Test category'}, format='json')
        self.assertEqual(category.status_code, 201)
        tag = self.client.post('/articles/api/v2/tags/', {'name': 'audit-tag'}, format='json')
        self.assertEqual(tag.status_code, 201)
        self.client.patch(f"/articles/api/v2/categories/{category.data['id']}/", {'name': 'Updated audit category'}, format='json')
        self.client.delete(f"/articles/api/v2/tags/{tag.data['id']}/")
        actions = set(AuditLog.objects.values_list('action', flat=True))
        self.assertTrue({'category_created', 'category_updated', 'tag_created', 'tag_archived'}.issubset(actions))
