from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, ArticleSource, ArticleSourceChunk, ArticleSourceDocument


class SourceIngestionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='source-editor', email='source-editor@example.com', password='StrongPass123!', role='Editor')
        self.article = Article.objects.create(title='A valid article title', content='The city council approved a climate budget for the coming year.', author=self.editor, email=self.editor.email, category='news', agreed_to_terms=True)
        self.source = ArticleSource.objects.create(article=self.article, title='Council budget report', publisher='City Council', url='https://example.com/report', source_type='primary')

    @override_settings(SOURCE_CHUNK_SIZE=300)
    @patch('articles.source_ingestion.requests.get')
    def test_html_source_is_extracted_chunked_and_retrievable(self, get):
        response = Mock()
        response.content = b'<html><body><h1>Budget report</h1><p>The council approved a climate budget for the coming year.</p></body></html>'
        response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        response.raise_for_status.return_value = None
        get.return_value = response
        self.client.force_authenticate(user=self.editor)

        ingest = self.client.post(f'/articles/api/v2/sources/{self.source.id}/ingest/', format='json')
        self.assertEqual(ingest.status_code, 201)
        self.assertEqual(ArticleSourceDocument.objects.get(source=self.source).status, 'ready')
        self.assertGreater(ArticleSourceChunk.objects.count(), 0)
        evidence = self.client.get(f'/articles/api/v2/sources/{self.source.id}/evidence/?q=climate budget')
        self.assertEqual(evidence.status_code, 200)
        self.assertIn('climate budget', evidence.data['evidence'][0]['passage'].lower())

    @patch('articles.source_ingestion.requests.get')
    def test_ai_fact_check_includes_exact_source_passage(self, get):
        response = Mock()
        response.content = b'<p>The city council approved a climate budget for the coming year.</p>'
        response.headers = {'Content-Type': 'text/html'}
        response.raise_for_status.return_value = None
        get.return_value = response
        self.client.force_authenticate(user=self.editor)
        self.client.post(f'/articles/api/v2/sources/{self.source.id}/ingest/', format='json')
        result = self.client.post(f'/articles/api/v2/articles/{self.article.id}/fact-checks/ai/', format='json')
        self.assertEqual(result.status_code, 200)
        citations = result.data['suggestions']['claims'][0]['source_citations']
        self.assertTrue(citations[0]['passage'])

    @override_settings(SOURCE_SSRF_PROTECTION=True)
    @patch('articles.source_ingestion.requests.get')
    def test_private_source_url_is_rejected_before_fetch(self, get):
        self.source.url = 'http://127.0.0.1/private'
        self.source.save(update_fields=['url'])
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            f'/articles/api/v2/sources/{self.source.id}/ingest/',
            format='json',
        )
        self.assertEqual(response.status_code, 422)
        get.assert_not_called()
