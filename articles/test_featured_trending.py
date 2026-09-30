from rest_framework.test import APITestCase

from users.models import CustomUser
from .models import Article, ArticleView


class FeaturedTrendingTests(APITestCase):
    def setUp(self):
        self.editor = CustomUser.objects.create_user(username='feature-editor', email='feature-editor@example.com', password='Password123!', role='Editor')
        self.author = CustomUser.objects.create_user(username='feature-author', email='feature-author@example.com', password='Password123!', role='Journalist')
        self.article = Article.objects.create(
            title='Featured article test', content='Content', author=self.author,
            agreed_to_terms=True, workflow_status='published', status='published', is_visible=True,
        )

    def test_editor_features_article_and_public_discovery_lists_it(self):
        self.client.force_authenticate(self.editor)
        response = self.client.patch(f'/articles/api/v2/articles/{self.article.id}/featured/', {'is_featured': True}, format='json')
        self.assertEqual(response.status_code, 200)
        ArticleView.objects.create(article=self.article, user=self.editor)
        self.client.force_authenticate(None)
        response = self.client.get('/articles/api/v2/discover/?mode=featured')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        response = self.client.get('/articles/api/v2/discover/?mode=trending')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
