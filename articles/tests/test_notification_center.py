from rest_framework.test import APITestCase

from users.models import CustomUser
from ..models import Notification


class NotificationCenterTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='notification-user', email='notification@example.com',
            password='Password123!', role='Journalist',
        )
        self.notification = Notification.objects.create(
            recipient=self.user, notification_type='published', message='Your article is live.',
        )

    def test_user_can_list_and_read_own_notifications(self):
        self.client.force_authenticate(self.user)
        response = self.client.get('/articles/api/v2/notifications/')
        self.assertEqual(response.status_code, 200)
        notifications = response.data.get('results', response.data)
        self.assertEqual(len(notifications), 1)
        response = self.client.patch(f'/articles/api/v2/notifications/{self.notification.id}/read/')
        self.assertEqual(response.status_code, 200)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_user_cannot_read_another_users_notification(self):
        other = CustomUser.objects.create_user(
            username='notification-other', email='notification-other@example.com',
            password='Password123!', role='Journalist',
        )
        self.client.force_authenticate(other)
        response = self.client.patch(f'/articles/api/v2/notifications/{self.notification.id}/read/')
        self.assertEqual(response.status_code, 404)
