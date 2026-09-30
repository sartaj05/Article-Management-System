from rest_framework.test import APITestCase

from users.models import CustomUser
from .models import Article


class SearchImprovementTests(APITestCase):
    def setUp(self):
        author = CustomUser.objects.create_user(username='search-author', email='search@example.com', password='Password123!', role='Journalist')
        Article.objects.create(title='Django Search Guide', content='Django content', author=author, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        Article.objects.create(title='Python News Today', content='Django mentioned in the body', author=author, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)

    def test_search_ranks_title_match_and_supports_autocomplete(self):
        response = self.client.get('/articles/api/v2/articles/search/?q=django&sort=relevance')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['title'], 'Django Search Guide')
        response = self.client.get('/articles/api/v2/articles/autocomplete/?q=Djan')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
