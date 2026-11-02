from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import AIJob, AIUsageEvent, Article, EditorialAssistantRun


class AIObservabilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='obs-editor', email='obs-editor@example.com', password='StrongPass123!', role='Editor')
        self.article = Article.objects.create(title='A valid article title', content='Observability article content.', author=self.editor, email=self.editor.email, category='news', agreed_to_terms=True)

    def test_observability_summarizes_ai_telemetry(self):
        AIUsageEvent.objects.create(user=self.editor, article=self.article, provider='local-rule-based', action='summarize', total_tokens=20, prompt_tokens=12, completion_tokens=8)
        AIJob.objects.create(requested_by=self.editor, article=self.article, action='summarize', status='completed')
        EditorialAssistantRun.objects.create(requested_by=self.editor, article=self.article, action='summarize', provider='local-rule-based', latency_ms=12)
        self.client.force_authenticate(user=self.editor)
        response = self.client.get('/articles/api/v2/assistant/observability/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['usage']['total_tokens'], 20)
        self.assertEqual(response.data['jobs']['by_status']['completed'], 1)
        self.assertEqual(response.data['runs']['average_latency_ms'], 12.0)
