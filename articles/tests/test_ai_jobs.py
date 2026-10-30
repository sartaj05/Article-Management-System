from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import AIJob, Article, EditorialAssistantRun


class AIJobTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='job-user', email='job-user@example.com', password='StrongPass123!', role='Journalist')
        self.article = Article.objects.create(title='A valid article title', content='A useful article body for an asynchronous AI job.', author=self.user, email=self.user.email, category='news', agreed_to_terms=True)

    @override_settings(AI_JOBS_ASYNC=False)
    def test_job_completes_and_creates_audited_assistant_run(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/articles/api/v2/assistant/jobs/', {'article_id': self.article.id, 'action': 'summarize', 'idempotency_key': 'summary-1'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'completed')
        self.assertEqual(AIJob.objects.get().attempts, 1)
        self.assertEqual(EditorialAssistantRun.objects.count(), 1)

    @override_settings(AI_JOBS_ASYNC=False)
    def test_idempotency_returns_existing_job(self):
        self.client.force_authenticate(user=self.user)
        first = self.client.post('/articles/api/v2/assistant/jobs/', {'article_id': self.article.id, 'action': 'headline', 'idempotency_key': 'same-key'}, format='json')
        second = self.client.post('/articles/api/v2/assistant/jobs/', {'article_id': self.article.id, 'action': 'headline', 'idempotency_key': 'same-key'}, format='json')
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(AIJob.objects.count(), 1)
