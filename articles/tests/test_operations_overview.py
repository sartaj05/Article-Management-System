from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import CustomUser, ReaderDigestDelivery, WebhookDelivery, WebhookEndpoint
from ..models import Article, ArticleAssignment, DistributionJob


class OperationsOverviewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(
            username='operations-editor', email='operations@example.com', password='StrongPass123!', role='Editor',
        )
        self.author = CustomUser.objects.create_user(
            username='operations-author', email='operations-author@example.com', password='StrongPass123!', role='Journalist',
        )
        self.article = Article.objects.create(
            title='Operations story', content='Content', author=self.author, agreed_to_terms=True,
        )
        self.client.force_authenticate(self.editor)

    def test_overview_aggregates_actionable_workflow_incidents(self):
        DistributionJob.objects.create(article=self.article, requested_by=self.author, channel='newsletter', status='failed')
        endpoint = WebhookEndpoint.objects.create(owner=self.editor, url='https://example.com/hooks', secret='secret')
        WebhookDelivery.objects.create(endpoint=endpoint, event_type='article.published', status='failed')
        ReaderDigestDelivery.objects.create(
            user=self.editor, frequency='daily', period_key=timezone.localdate(), status='failed', last_error='Mail provider unavailable',
        )
        ArticleAssignment.objects.create(
            article=self.article, editor=self.editor, due_at=timezone.now() - timedelta(hours=2), status='in_progress',
        )
        response = self.client.get('/articles/api/v2/operations/overview/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'attention')
        self.assertEqual(response.data['summary']['distribution_failed'], 1)
        self.assertEqual(response.data['summary']['webhook_failed'], 1)
        self.assertEqual(response.data['summary']['digest_failed'], 1)
        self.assertEqual(response.data['summary']['overdue_assignments'], 1)
        self.assertEqual(len(response.data['incidents']), 4)

    def test_journalists_cannot_view_operations_overview(self):
        self.client.force_authenticate(self.author)
        response = self.client.get('/articles/api/v2/operations/overview/')
        self.assertEqual(response.status_code, 403)
