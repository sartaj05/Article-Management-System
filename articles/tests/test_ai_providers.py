import json
from unittest.mock import Mock, patch
from urllib.error import URLError

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import CustomUser
from ..ai_providers import AIProviderError, OpenAICompatibleProvider
from ..models import Article, EditorialAssistantRun


class EditorialAIProviderTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.journalist = CustomUser.objects.create_user(
            username='ai-journalist', email='ai-journalist@example.com',
            password='StrongPass123!', role='Journalist',
        )
        self.article = Article.objects.create(
            title='A valid article title',
            content='Article content for testing a structured AI response.',
            author=self.journalist,
            email=self.journalist.email,
            category='news',
            agreed_to_terms=True,
        )

    @override_settings(AI_ASSISTANT_API_KEY='test-key')
    def test_openai_provider_parses_structured_json(self):
        response = Mock()
        response.read.return_value = json.dumps({
            'choices': [{'message': {'content': json.dumps({'summary': 'A reviewed summary.'})}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 6, 'total_tokens': 16},
        }).encode('utf-8')
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch('articles.ai_providers.urlopen', return_value=response):
            result = OpenAICompatibleProvider().generate(self.article, 'summarize')

        self.assertEqual(result.provider, 'openai')
        self.assertEqual(result.suggestions['summary'], 'A reviewed summary.')
        self.assertEqual(result.metadata['usage']['total_tokens'], 16)

    @override_settings(AI_ASSISTANT_API_KEY='test-key')
    def test_openai_provider_rejects_invalid_schema(self):
        response = Mock()
        response.read.return_value = json.dumps({
            'choices': [{'message': {'content': json.dumps({'wrong': 'shape'})}}],
        }).encode('utf-8')
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch('articles.ai_providers.urlopen', return_value=response):
            with self.assertRaises(AIProviderError):
                OpenAICompatibleProvider().generate(self.article, 'summarize')

    @override_settings(
        AI_ASSISTANT_PROVIDER='openai',
        AI_ASSISTANT_API_KEY='test-key',
        AI_ASSISTANT_FALLBACK_ENABLED=True,
    )
    def test_api_falls_back_and_audits_provider_failure(self):
        self.client.force_authenticate(user=self.journalist)
        with patch('articles.ai_providers.urlopen', side_effect=URLError('provider unavailable')):
            response = self.client.post(
                f'/articles/api/v2/articles/{self.article.id}/assistant/',
                {'action': 'seo'}, format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['provider'], 'local-rule-based-fallback')
        self.assertIn('fallback_reason', response.data['metadata'])
        run = EditorialAssistantRun.objects.get(pk=response.data['run_id'])
        self.assertEqual(run.model, 'rules-v1')
        self.assertGreaterEqual(run.latency_ms, 0)
