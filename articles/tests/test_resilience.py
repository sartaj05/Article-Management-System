from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.core.management import call_command

from config.resilience import CircuitOpenError, call_with_circuit
from users.models import CustomUser
from articles.models import Article, DistributionJob


class CircuitBreakerTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @override_settings(PROVIDER_CIRCUIT_FAILURE_THRESHOLD=2, PROVIDER_CIRCUIT_COOLDOWN_SECONDS=60)
    def test_circuit_opens_after_repeated_provider_failures(self):
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                call_with_circuit('test-provider', Mock(side_effect=RuntimeError('down')))
        with self.assertRaises(CircuitOpenError):
            call_with_circuit('test-provider', Mock(return_value=True))


class ProviderRetryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = CustomUser.objects.create_user(username='retry-author', email='retry-author@example.com', password='StrongPass123!', role='Journalist')
        self.article = Article.objects.create(title='Retryable provider story', content='Content', author=self.user, agreed_to_terms=True)

    @override_settings(NEWSLETTER_PROVIDER_URL='https://newsletter.example.test/send', NEWSLETTER_PROVIDER_TOKEN='token', PROVIDER_RETRY_BASE_SECONDS=10)
    @patch('articles.distribution_providers.requests.post')
    def test_provider_failure_is_scheduled_for_exponential_retry(self, post):
        post.return_value = Mock(status_code=503, content=b'{}', headers={})
        job = DistributionJob.objects.create(article=self.article, requested_by=self.user, channel='newsletter')
        call_command('process_distribution_jobs')
        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertIsNotNone(job.scheduled_for)
        self.assertEqual(job.attempts, 1)
