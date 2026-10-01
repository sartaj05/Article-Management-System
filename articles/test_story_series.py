from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from .models import Article, SeriesArticle


class StorySeriesFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(
            username='series-editor', email='series-editor@example.com', password='StrongPass123!', role='Editor',
        )
        self.article = Article.objects.create(
            title='A story for the series', content='Series content', author=self.editor,
            author_name=self.editor.username, email=self.editor.email, agreed_to_terms=True,
            workflow_status='published', status='published', is_visible=True,
        )
        self.client.force_authenticate(self.editor)

    def test_editor_can_create_series_and_add_article(self):
        response = self.client.post('/articles/api/v2/series/', {
            'title': 'Climate desk', 'description': 'Our climate coverage', 'is_published': True,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['slug'], 'climate-desk')

        response = self.client.post('/articles/api/v2/series/climate-desk/', {
            'article_id': self.article.id, 'position': 1,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(SeriesArticle.objects.filter(series__slug='climate-desk', article=self.article).exists())

        response = self.client.get('/articles/api/v2/series/climate-desk/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['articles'][0]['title'], self.article.title)
