from rest_framework.test import APITestCase

from users.models import CustomUser
from .models import Article


class SEOTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='seo-author', email='seo@example.com', password='Password123!', role='Journalist')
        self.article = Article.objects.create(title='SEO article test', content='Content', author=self.author, agreed_to_terms=True)

    def test_author_can_update_article_seo_metadata(self):
        self.client.force_authenticate(self.author)
        response = self.client.patch(
            f'/articles/api/v2/articles/{self.article.id}/seo/',
            {
                'meta_title': 'SEO article title',
                'meta_description': 'A useful article description for search engines.',
                'seo_keywords': 'django, articles, publishing',
                'canonical_url': 'https://example.com/articles/seo-article/',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.meta_title, 'SEO article title')
        self.assertEqual(self.article.canonical_url, 'https://example.com/articles/seo-article/')
