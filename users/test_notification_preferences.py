from rest_framework.test import APITestCase

from articles.models import Article, Notification
from articles.notifications import notify
from .models import CustomUser, NotificationPreference


class NotificationPreferenceTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='preferences-user', email='preferences@example.com', password='Password123!', role='Journalist')

    def test_user_can_update_preferences_and_disable_in_app_workflow_alerts(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch('/api/notification-preferences/', {'in_app_enabled': False, 'workflow_enabled': False}, format='json')
        self.assertEqual(response.status_code, 200)
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(preference.in_app_enabled)
        article = Article.objects.create(title='Preference article test', content='Content', author=self.user, agreed_to_terms=True)
        notify(recipient=self.user, article=article, notification_type='published', message='Published')
        self.assertFalse(Notification.objects.filter(recipient=self.user).exists())
