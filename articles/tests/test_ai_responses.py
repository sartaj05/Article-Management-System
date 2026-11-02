import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from ..ai_providers import OpenAIResponsesProvider
from types import SimpleNamespace


class ResponsesProviderTests(TestCase):
    def setUp(self):
        self.article = SimpleNamespace(title='A valid article title', content='A short article about a newsroom update.')

    @override_settings(AI_ASSISTANT_API_KEY='test-key')
    def test_responses_provider_parses_output_text_and_usage(self):
        response = Mock()
        response.read.return_value = json.dumps({
            'output_text': json.dumps({'summary': 'A structured response.'}),
            'usage': {'input_tokens': 12, 'output_tokens': 7, 'total_tokens': 19},
        }).encode('utf-8')
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('articles.ai_providers.urlopen', return_value=response):
            result = OpenAIResponsesProvider().generate(self.article, 'summarize')
        self.assertEqual(result.provider, 'openai-responses')
        self.assertEqual(result.suggestions['summary'], 'A structured response.')
        self.assertEqual(result.metadata['usage']['total_tokens'], 19)

    @override_settings(AI_ASSISTANT_API_KEY='test-key')
    def test_responses_stream_emits_typed_deltas(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.__iter__ = Mock(return_value=iter([
            b'data: {"type":"response.output_text.delta","delta":"Hello"}\n',
            b'data: {"type":"response.completed","response":{}}\n',
            b'data: [DONE]\n',
        ]))
        with patch('articles.ai_providers.urlopen', return_value=response):
            events = list(OpenAIResponsesProvider().stream_generate(self.article, 'summarize'))
        self.assertEqual(events[0]['delta'], 'Hello')
        self.assertEqual(events[1]['type'], 'response.completed')
