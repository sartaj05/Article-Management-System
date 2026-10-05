from rest_framework.test import APITestCase

from users.models import CustomUser
from ..models import Article, ModerationFlag


class ModerationTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='moderation-author', email='moderation@example.com', password='Password123!', role='Journalist')
        self.article = Article.objects.create(title='Moderation article test', content='Buy now for free money and guaranteed profit.', author=self.author, agreed_to_terms=True)

    def test_high_risk_content_is_flagged_and_submission_is_blocked(self):
        self.client.force_authenticate(self.author)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/moderation/')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(ModerationFlag.objects.filter(article=self.article, severity='high').exists())
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/submit/')
        self.assertEqual(response.status_code, 400)
        self.article.refresh_from_db()
        self.assertEqual(self.article.workflow_status, 'draft')
