from rest_framework.test import APITestCase

from users.models import CustomUser
from .models import Article, ArticleRevision


class RevisionCompareTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='compare-author', email='compare@example.com', password='Password123!', role='Journalist')
        self.article = Article.objects.create(title='Revision compare test', content='First paragraph', author=self.author, agreed_to_terms=True)
        self.left = ArticleRevision.objects.create(article=self.article, editor=self.author, title=self.article.title, content='First paragraph', summary='First')
        self.right = ArticleRevision.objects.create(article=self.article, editor=self.author, title=self.article.title, content='First paragraph\nSecond paragraph', summary='Second')

    def test_author_can_compare_two_revisions(self):
        self.client.force_authenticate(self.author)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/revisions/compare/?from={self.left.id}&to={self.right.id}')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['changed'])
        self.assertTrue(any(line.startswith('+Second paragraph') for line in response.data['content_diff']))
