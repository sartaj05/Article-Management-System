from django.test import TestCase
from rest_framework.test import APIClient

from articles.models import Article, DistributionJob
from users.models import CustomUser, Workspace, WorkspaceMembership


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(
            username='tenant-editor', email='tenant-editor@example.com',
            password='StrongPass123!', role='Editor',
        )
        self.first = Workspace.objects.create(name='First newsroom', slug='first-newsroom', owner=self.editor)
        self.second = Workspace.objects.create(name='Second newsroom', slug='second-newsroom', owner=self.editor)
        WorkspaceMembership.objects.create(workspace=self.first, user=self.editor, role='owner')
        WorkspaceMembership.objects.create(workspace=self.second, user=self.editor, role='owner')
        self.first_article = Article.objects.create(
            title='First newsroom story', content='First content', author=self.editor,
            workspace=self.first, workflow_status='published', is_visible=True,
        )
        self.second_article = Article.objects.create(
            title='Second newsroom story', content='Second content', author=self.editor,
            workspace=self.second, workflow_status='published', is_visible=True,
        )
        DistributionJob.objects.create(article=self.first_article, requested_by=self.editor, channel='rss')
        DistributionJob.objects.create(article=self.second_article, requested_by=self.editor, channel='rss')
        self.client.force_authenticate(self.editor)

    def test_non_member_workspace_is_rejected(self):
        outsider = CustomUser.objects.create_user(
            username='tenant-outsider', email='tenant-outsider@example.com',
            password='StrongPass123!', role='Editor',
        )
        self.client.force_authenticate(outsider)
        response = self.client.get('/articles/api/v2/operations/overview/', HTTP_X_WORKSPACE_SLUG=self.first.slug)
        self.assertEqual(response.status_code, 403)

    def test_operations_are_scoped_to_selected_workspace(self):
        response = self.client.get('/articles/api/v2/operations/overview/', HTTP_X_WORKSPACE_SLUG=self.first.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['summary']['distribution_queued'], 1)

    def test_distribution_jobs_do_not_cross_tenants(self):
        response = self.client.get('/articles/api/v2/distribution-jobs/', HTTP_X_WORKSPACE_SLUG=self.first.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['jobs'][0]['article_id'], self.first_article.id)

    def test_executive_analytics_is_scoped_to_selected_workspace(self):
        response = self.client.get('/articles/api/v2/analytics/executive/', HTTP_X_WORKSPACE_SLUG=self.first.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['content']['published'], 1)
