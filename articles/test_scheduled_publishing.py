from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from users.models import CustomUser
from .models import Article


class ScheduledPublishingTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='scheduled-author', email='scheduled@example.com', password='Password123!', role='Journalist')
        self.editor = CustomUser.objects.create_user(username='scheduled-editor', email='editor-scheduled@example.com', password='Password123!', role='Editor')
        self.article = Article.objects.create(
            title='Scheduled article test', content='Content', author=self.author,
            agreed_to_terms=True, workflow_status='approved', review_status='approved',
        )

    def test_editor_can_schedule_and_command_publishes_article(self):
        self.client.force_authenticate(self.editor)
        scheduled_at = timezone.now() + timedelta(hours=1)
        response = self.client.post(
            f'/articles/api/v2/articles/{self.article.id}/schedule/',
            {'scheduled_publish_at': scheduled_at.isoformat()},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.article.scheduled_publish_at = timezone.now() - timedelta(minutes=1)
        self.article.save(update_fields=['scheduled_publish_at'])
        call_command('publish_scheduled_articles')
        self.article.refresh_from_db()
        self.assertEqual(self.article.workflow_status, 'published')
        self.assertTrue(self.article.is_visible)
