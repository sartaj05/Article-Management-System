from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from .models import Article, ArticleCorrection, ArticleProvenance


class TrustCenterFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(
            username='trust-editor', email='trust-editor@example.com', password='StrongPass123!', role='Editor',
        )
        self.article = Article.objects.create(
            title='Trust center article', content='Verified content', author=self.editor,
            author_name=self.editor.username, email=self.editor.email, agreed_to_terms=True,
            workflow_status='published', status='published', is_visible=True,
        )
        self.client.force_authenticate(self.editor)

    def test_editor_can_publish_correction_and_provenance(self):
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/corrections/', {
            'original_text': 'Old fact', 'corrected_text': 'Correct fact', 'reason': 'The source was updated.',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ArticleCorrection.objects.get().status, 'published')

        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/provenance/', {
            'origin': 'assisted', 'tool_name': 'Editorial assistant',
            'disclosure': 'A human editor reviewed the final copy.', 'sources_reviewed': True,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ArticleProvenance.objects.get().origin, 'assisted')

        self.client.force_authenticate(None)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/corrections/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
