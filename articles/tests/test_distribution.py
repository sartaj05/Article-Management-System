from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser, WebhookEndpoint
from ..models import Article, DistributionJob


class DistributionAutomationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = CustomUser.objects.create_user(username='distribution-author', email='distribution@example.com', password='StrongPass123!', role='Journalist')
        self.article = Article.objects.create(title='Distribution story', content='Content', author=self.author, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)

    def test_idempotency_key_returns_the_same_distribution_job(self):
        self.client.force_authenticate(self.author)
        payload = {'article_id': self.article.id, 'channel': 'newsletter'}
        first = self.client.post('/articles/api/v2/distribution-jobs/', payload, format='json', HTTP_IDEMPOTENCY_KEY='distribution-once')
        second = self.client.post('/articles/api/v2/distribution-jobs/', payload, format='json', HTTP_IDEMPOTENCY_KEY='distribution-once')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertTrue(second.data['deduplicated'])

    @patch('users.delivery.requests.post')
    def test_worker_delivers_webhook_job_and_records_attempt(self, post):
        post.return_value = Mock(status_code=204)
        WebhookEndpoint.objects.create(owner=self.author, url='https://hooks.example.com/articles', secret='secret')
        job = DistributionJob.objects.create(article=self.article, requested_by=self.author, channel='webhook', idempotency_key='worker-once')
        call_command('process_distribution_jobs')
        job.refresh_from_db()
        self.assertEqual(job.status, 'delivered')
        self.assertEqual(job.attempts, 1)
        self.assertIsNotNone(job.last_attempt_at)

    def test_failed_job_can_be_requeued(self):
        job = DistributionJob.objects.create(article=self.article, requested_by=self.author, channel='social', status='failed', last_error='Provider unavailable')
        self.client.force_authenticate(self.author)
        response = self.client.patch(f'/articles/api/v2/distribution-jobs/{job.id}/', format='json')
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(job.last_error, '')

    def test_control_center_returns_health_and_failure_alert(self):
        DistributionJob.objects.create(article=self.article, requested_by=self.author, channel='newsletter', status='failed', last_error='Newsletter provider timed out')
        DistributionJob.objects.create(article=self.article, requested_by=self.author, channel='rss', status='delivered')
        self.client.force_authenticate(self.author)
        response = self.client.get('/articles/api/v2/distribution-jobs/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['failure_alert']['active'])
        self.assertEqual(response.data['failure_alert']['count'], 1)
        health = {item['channel']: item for item in response.data['provider_health']}
        self.assertEqual(health['newsletter']['status'], 'degraded')
        self.assertEqual(health['rss']['status'], 'healthy')
