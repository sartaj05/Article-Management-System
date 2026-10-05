from rest_framework.test import APITestCase

from users.models import CustomUser
from ..models import Article, AuditLog


class AuditLogTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='audit-author', email='audit@example.com', password='Password123!', role='Journalist')
        self.editor = CustomUser.objects.create_user(username='audit-editor', email='audit-editor@example.com', password='Password123!', role='Editor')
        self.article = Article.objects.create(title='Audit article test', content='Content', author=self.author, agreed_to_terms=True)

    def test_article_submission_is_logged_and_editor_can_filter_logs(self):
        self.client.force_authenticate(self.author)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/submit/')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.editor)
        response = self.client.get(f'/articles/api/v2/audit-logs/?article_id={self.article.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['action'], 'article_submitted')
        self.assertTrue(AuditLog.objects.filter(article=self.article).exists())
