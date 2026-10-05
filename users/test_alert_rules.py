from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from articles.models import Article
from .models import AlertRule, CustomUser, PushSubscription
from .delivery import dispatch_article_alert


class AlertRuleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.reader = CustomUser.objects.create_user(username='alert-reader', email='alert-reader@example.com', password='StrongPass123!', role='Journalist')
        self.author = CustomUser.objects.create_user(username='alert-author', email='alert-author@example.com', password='StrongPass123!', role='Journalist')
        self.article = Article.objects.create(title='Alert article title', content='Alert content', author=self.author, category='news', agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        PushSubscription.objects.create(user=self.reader, endpoint='https://push.example/reader', p256dh='key', auth='auth')
        self.client.force_authenticate(self.reader)

    def test_reader_can_manage_alert_rules(self):
        response = self.client.post('/api/alerts/rules/', {'rule_type': 'category', 'value': 'news'}, format='json')
        self.assertEqual(response.status_code, 201)
        response = self.client.get('/api/alerts/rules/')
        self.assertEqual(len(response.data), 1)
        response = self.client.patch(f"/api/alerts/rules/{response.data[0]['id']}/", {'is_active': False}, format='json')
        self.assertFalse(response.data['is_active'])

    @patch('users.delivery.send_web_push')
    def test_matching_rule_dispatches_push_alert(self, send_push):
        send_push.return_value = {'sent': False, 'reason': 'test'}
        AlertRule.objects.create(user=self.reader, rule_type='category', value='news')
        results = dispatch_article_alert(article=self.article)
        self.assertEqual(len(results), 1)
        send_push.assert_called_once()
