from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from .models import Notification


class NotificationBadgeTests(TestCase):
    def test_unread_count_endpoint_returns_current_count(self):
        user = CustomUser.objects.create_user(username='badge-reader', email='badge@example.com', password='StrongPass123!', role='Journalist')
        Notification.objects.create(recipient=user, notification_type='reader_alert', message='Unread')
        Notification.objects.create(recipient=user, notification_type='reader_alert', message='Read', is_read=True)
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get('/articles/api/v2/notifications/unread-count/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'count': 1})
