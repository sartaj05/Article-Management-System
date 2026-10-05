from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, ArticleFactCheck, ArticleSource


class EvidenceSummaryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='evidence-editor', email='evidence-editor@example.com', password='StrongPass123!', role='Editor')
        self.article = Article.objects.create(title='Evidence summary article', content='Content', author=self.editor, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        self.client.force_authenticate(self.editor)

    def test_evidence_endpoint_summarizes_sources_and_verdicts(self):
        ArticleSource.objects.create(article=self.article, url='https://example.com/source', title='Primary source', source_type='primary', added_by=self.editor)
        ArticleFactCheck.objects.create(article=self.article, claim='A tested claim', verdict='verified', explanation='Checked against the primary source.', checked_by=self.editor)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/evidence/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['primary_source_count'], 1)
        self.assertEqual(response.data['verified_claims'], 1)
        self.assertEqual(response.data['quality_status'], 'reviewed')
