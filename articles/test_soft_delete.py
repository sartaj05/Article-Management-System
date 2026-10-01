from rest_framework.test import APITestCase

from users.models import CustomUser
from .models import Article


class SoftDeleteTests(APITestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(username='trash-admin', email='trash-admin@example.com', password='Password123!', role='Admin')
        self.article = Article.objects.create(title='Soft delete article', content='Content', author=self.admin, agreed_to_terms=True)

    def test_trash_hides_article_and_restore_recovers_it(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/trash/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Article.objects.filter(pk=self.article.id).exists())
        self.assertTrue(Article.all_objects.filter(pk=self.article.id, is_deleted=True).exists())

        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/restore/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Article.objects.filter(pk=self.article.id).exists())
