from unittest.mock import patch

from django.test import TestCase, override_settings

from users.models import CustomUser
from ..models import Article, DistributionJob
from ..operations import refresh_operational_alerts


class ObservabilityAlertTests(TestCase):
    def setUp(self):
        self.editor = CustomUser.objects.create_user(username='otel-editor', email='otel@example.com', password='StrongPass123!', role='Editor')
        self.article = Article.objects.create(
            title='Observability alert', content='Operations content', author=self.editor,
            author_name=self.editor.username, email=self.editor.email, agreed_to_terms=True,
        )

    @override_settings(OPS_ALERT_WEBHOOK_URL='https://hooks.example.test/ops', OPS_ALERT_WEBHOOK_PROVIDER='teams')
    @patch('articles.operations.requests.post')
    def test_new_alert_is_sent_once_to_configured_webhook(self, post):
        post.return_value.raise_for_status.return_value = None
        DistributionJob.objects.create(article=self.article, requested_by=self.editor, channel='rss', status='failed')
        first = refresh_operational_alerts()
        second = refresh_operational_alerts()
        self.assertTrue(first['notifications']['sent'])
        self.assertFalse(second['notifications']['sent'])
        self.assertEqual(post.call_count, 1)
        self.assertIn('operational alert', post.call_args.kwargs['json']['text'])
