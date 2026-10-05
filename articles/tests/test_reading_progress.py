from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, ReadingProgress


class ReadingProgressTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='reader-progress', email='reader-progress@example.com', password='StrongPass123!', role='Journalist')
        self.article = Article.objects.create(title='Reading progress article', content='Content', author=self.user, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        self.client.force_authenticate(self.user)

    def test_reader_can_save_and_resume_progress(self):
        response = self.client.patch(f'/articles/api/v2/articles/{self.article.id}/progress/', {'progress_percent': 45, 'position_seconds': 120}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['completed'])
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/progress/')
        self.assertEqual(response.data['progress_percent'], 45)
        response = self.client.patch(f'/articles/api/v2/articles/{self.article.id}/progress/', {'progress_percent': 100}, format='json')
        self.assertTrue(response.data['completed'])
        self.assertEqual(ReadingProgress.objects.get().position_seconds, 120)

    def test_progress_rejects_invalid_percent(self):
        response = self.client.patch(f'/articles/api/v2/articles/{self.article.id}/progress/', {'progress_percent': 101}, format='json')
        self.assertEqual(response.status_code, 400)
