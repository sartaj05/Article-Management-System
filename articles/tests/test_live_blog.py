from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, ArticleLiveUpdate


class LiveBlogFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='live-editor', email='live-editor@example.com', password='StrongPass123!', role='Editor',
        )
        self.article = Article.objects.create(
            title='Live election update', content='Initial live coverage', author=self.user,
            author_name=self.user.username, email=self.user.email, agreed_to_terms=True,
            workflow_status='published', status='published', is_visible=True,
        )
        self.client.force_authenticate(self.user)

    def test_editor_can_start_live_blog_and_publish_update(self):
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/live/', {'action': 'start'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_live'])

        response = self.client.post(
            f'/articles/api/v2/articles/{self.article.id}/live/',
            {'body': 'Officials have released the first results.', 'is_pinned': True},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ArticleLiveUpdate.objects.get().body, 'Officials have released the first results.')

        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/live/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['updates']), 1)

    def test_editor_can_end_live_blog(self):
        self.client.post(f'/articles/api/v2/articles/{self.article.id}/live/', {'action': 'start'}, format='json')
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/live/', {'action': 'end'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_live'])
