from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from .models import Article


class HeadlessAPIFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(
            username='api-editor', email='api-editor@example.com', password='StrongPass123!', role='Editor',
        )
        self.article = Article.objects.create(
            title='Public API article', content='Published API content', author=self.editor,
            author_name=self.editor.username, email=self.editor.email, agreed_to_terms=True,
            workflow_status='published', status='published', is_visible=True,
        )

    def test_api_key_can_read_public_headless_feed(self):
        self.client.force_authenticate(self.editor)
        response = self.client.post('/api/developer/keys/', {'name': 'Website frontend'}, format='json')
        self.assertEqual(response.status_code, 201)
        raw_key = response.data['key']

        self.client.force_authenticate(None)
        response = self.client.get('/articles/api/v2/public/articles/', HTTP_X_API_KEY=raw_key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['slug'], self.article.slug)

    def test_invalid_key_is_rejected_and_docs_are_public(self):
        response = self.client.get('/articles/api/v2/public/articles/', HTTP_X_API_KEY='as_invalid')
        self.assertEqual(response.status_code, 401)
        response = self.client.get('/api/developer.json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('articles', response.data['endpoints'])
