from django.test import TestCase
from rest_framework.test import APIClient

from articles.models import Article
from users.models import CustomUser, Workspace, WorkspaceMembership


class ExecutiveReportingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='report-editor', email='report-editor@example.com', password='StrongPass123!', role='Editor')
        self.workspace = Workspace.objects.create(name='Reporting newsroom', slug='reporting-newsroom', owner=self.editor)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.editor, role='owner')
        Article.objects.create(title='Reporting published story', content='Content', author=self.editor, workspace=self.workspace, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        self.client.force_authenticate(self.editor)

    def test_executive_snapshot_includes_company_metrics_and_csv_export(self):
        response = self.client.get('/articles/api/v2/analytics/executive/', HTTP_X_WORKSPACE_SLUG=self.workspace.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['workspace_scope'], self.workspace.slug)
        self.assertIn('productivity', response.data)
        self.assertIn('ai', response.data)
        export = self.client.get('/articles/api/v2/analytics/executive/export/', HTTP_X_WORKSPACE_SLUG=self.workspace.slug)
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export['Content-Type'], 'text/csv')
        self.assertIn('productivity', export.content.decode())
