from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article


class ExecutiveAnalyticsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='exec-editor', email='exec-editor@example.com', password='StrongPass123!', role='Editor')
        self.journalist = CustomUser.objects.create_user(username='exec-journalist', email='exec-journalist@example.com', password='StrongPass123!', role='Journalist')
        Article.objects.create(title='Executive analytics story', content='Content', author=self.journalist, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)

    def test_editor_can_load_executive_snapshot(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get('/articles/api/v2/analytics/executive/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['content']['published'], 1)
        self.assertIn('membership', response.data)
        self.assertIn('distribution', response.data)
        self.assertIn('notifications', response.data)

    def test_journalist_cannot_load_executive_snapshot(self):
        self.client.force_authenticate(self.journalist)
        response = self.client.get('/articles/api/v2/analytics/executive/')
        self.assertEqual(response.status_code, 403)
