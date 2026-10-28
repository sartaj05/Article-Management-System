from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from users.models import CustomUser
from ..models import Article, DistributionJob


class DistributionProviderTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='provider-author', email='provider@example.com', password='StrongPass123!', role='Journalist')
        self.article = Article.objects.create(title='Provider distribution story', content='Content', author=self.user, agreed_to_terms=True)

    @override_settings(NEWSLETTER_PROVIDER_URL='https://newsletter.example.test/send', NEWSLETTER_PROVIDER_TOKEN='token')
    @patch('articles.distribution_providers.requests.post')
    def test_newsletter_provider_delivery_records_reference(self, post):
        post.return_value = Mock(status_code=202, content=b'{"id":"newsletter-123"}', headers={})
        job = DistributionJob.objects.create(article=self.article, requested_by=self.user, channel='newsletter')
        call_command('process_distribution_jobs')
        job.refresh_from_db()
        self.assertEqual(job.status, 'delivered')
        self.assertEqual(job.provider_reference, 'newsletter-123')
        post.assert_called_once()

    def test_unconfigured_social_provider_waits_for_configuration(self):
        job = DistributionJob.objects.create(article=self.article, requested_by=self.user, channel='social')
        call_command('process_distribution_jobs')
        job.refresh_from_db()
        self.assertEqual(job.status, 'awaiting_provider')
