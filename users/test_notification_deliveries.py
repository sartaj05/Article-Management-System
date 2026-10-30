from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from articles.models import Article, Notification
from articles.notifications import notify
from users.models import CustomUser, NotificationDelivery


class NotificationDeliveryTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='delivery-reader', email='delivery@example.com', password='StrongPass123!', role='Journalist')
        self.article = Article.objects.create(title='Delivery story', content='Content', author=self.user, agreed_to_terms=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('users.delivery.send_mail', return_value=1)
    def test_email_notification_is_logged_and_listed(self, send_mail):
        notify(recipient=self.user, article=self.article, notification_type='published', message='Published story')
        delivery = NotificationDelivery.objects.get(recipient=self.user, channel='email')
        self.assertEqual(delivery.status, 'sent')
        self.assertEqual(delivery.attempts, 1)
        response = self.client.get('/api/notification-deliveries/?channel=email')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['status'], 'sent')
        send_mail.assert_called_once()

    @patch('users.delivery.send_mail', side_effect=RuntimeError('SMTP unavailable'))
    def test_failed_email_delivery_can_be_retried(self, send_mail):
        notify(recipient=self.user, article=self.article, notification_type='published', message='Retry story')
        delivery = NotificationDelivery.objects.get(recipient=self.user, channel='email')
        self.assertEqual(delivery.status, 'failed')
        send_mail.side_effect = None
        response = self.client.post('/api/notification-deliveries/', {'delivery_id': delivery.id}, format='json')
        self.assertEqual(response.status_code, 200)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'sent')
        self.assertEqual(delivery.attempts, 2)
