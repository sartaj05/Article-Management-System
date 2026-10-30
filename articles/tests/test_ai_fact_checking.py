from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, ArticleFactCheck, ArticleSource


class AIFactCheckingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.journalist = CustomUser.objects.create_user(username='fact-journalist', email='fact-journalist@example.com', password='StrongPass123!', role='Journalist')
        self.editor = CustomUser.objects.create_user(username='fact-editor', email='fact-editor@example.com', password='StrongPass123!', role='Editor')
        self.article = Article.objects.create(title='A valid article title', content='The city council approved a new climate budget. Analysts expect the program to create jobs.', author=self.journalist, email=self.journalist.email, category='news', agreed_to_terms=True)
        self.source = ArticleSource.objects.create(article=self.article, title='City council budget report', publisher='City Council', url='https://example.com/budget', source_type='primary', notes='The council approved the climate budget.')

    @override_settings(AI_ASSISTANT_PROVIDER='local-rule-based')
    def test_ai_fact_check_returns_citations_and_applies_pending_claims(self):
        self.client.force_authenticate(user=self.journalist)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/fact-checks/ai/', format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['requires_review'])
        self.assertEqual(response.data['source_count'], 1)
        self.assertTrue(response.data['suggestions']['claims'][0]['source_citations'])

        self.client.force_authenticate(user=self.editor)
        apply_response = self.client.post(f"/articles/api/v2/assistant/runs/{response.data['run_id']}/fact-check/apply/", {'claim_indexes': [0]}, format='json')
        self.assertEqual(apply_response.status_code, 201)
        check = ArticleFactCheck.objects.get()
        self.assertEqual(check.review_status, 'pending')
        self.assertTrue(check.is_ai_suggested)
        self.assertEqual(list(check.supporting_sources.values_list('id', flat=True)), [self.source.id])

    def test_journalist_cannot_apply_ai_fact_check(self):
        self.client.force_authenticate(user=self.journalist)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/fact-checks/ai/', format='json')
        apply_response = self.client.post(f"/articles/api/v2/assistant/runs/{response.data['run_id']}/fact-check/apply/", format='json')
        self.assertEqual(apply_response.status_code, 403)
