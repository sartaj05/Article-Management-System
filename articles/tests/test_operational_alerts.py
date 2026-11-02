from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, DistributionJob, OperationalAlert
from ..operations import refresh_operational_alerts


class OperationalAlertTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='ops-editor', email='ops-editor@example.com', password='StrongPass123!', role='Editor',
        )
        self.article = Article.objects.create(
            title='Operations article', content='Operations content', author=self.user,
            author_name=self.user.username, email=self.user.email, agreed_to_terms=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_refresh_persists_and_increments_failed_job_alert(self):
        DistributionJob.objects.create(article=self.article, requested_by=self.user, channel='rss', status='failed')
        first = refresh_operational_alerts()
        alert = OperationalAlert.objects.get(fingerprint='distribution.failed')
        self.assertEqual(alert.status, 'open')
        self.assertEqual(alert.occurrences, 1)
        second = refresh_operational_alerts()
        alert.refresh_from_db()
        self.assertEqual(len(first['alerts']), 1)
        self.assertEqual(len(second['alerts']), 1)
        self.assertEqual(alert.occurrences, 2)

    def test_editor_can_acknowledge_operational_alert(self):
        DistributionJob.objects.create(article=self.article, requested_by=self.user, channel='rss', status='failed')
        refresh_operational_alerts()
        alert = OperationalAlert.objects.get(fingerprint='distribution.failed')
        response = self.client.post('/articles/api/v2/operations/alerts/', {'alert_id': alert.id, 'action': 'acknowledge'}, format='json')
        self.assertEqual(response.status_code, 200)
        alert.refresh_from_db()
        self.assertEqual(alert.status, 'acknowledged')
