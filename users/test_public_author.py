from rest_framework.test import APITestCase

from articles.models import Article
from .models import CustomUser, Profile


class PublicAuthorTests(APITestCase):
    def test_public_author_page_contains_only_published_articles(self):
        author = CustomUser.objects.create_user(username='public-author', email='public-author@example.com', password='Password123!', role='Journalist')
        Profile.objects.create(user=author, bio='A public author biography.')
        Article.objects.create(title='Public author article', content='Published content', author=author, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        Article.objects.create(title='Private author article', content='Draft content', author=author, agreed_to_terms=True)
        response = self.client.get(f'/api/authors/{author.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['published_count'], 1)
        self.assertEqual(response.data['bio'], 'A public author biography.')
        self.assertEqual(len(response.data['articles']), 1)
