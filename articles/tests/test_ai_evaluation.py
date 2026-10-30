from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import AIEvaluationCase, AIEvaluationRun, AIPromptVersion


class AIEvaluationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='eval-editor', email='eval-editor@example.com', password='StrongPass123!', role='Editor')
        AIPromptVersion.objects.create(name='editorial-copilot', version='editorial-v2', system_prompt='Use only verified facts.')
        AIEvaluationCase.objects.create(name='summary-has-output', action='summarize', title='A valid article title', content='A long article about climate policy and a community response.', criteria={'required_keys': ['summary'], 'non_empty': ['summary']})

    def test_evaluation_run_scores_golden_case(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post('/articles/api/v2/assistant/evaluations/', format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['prompt_version'], 'editorial-v2')
        self.assertEqual(response.data['score'], 100.0)
        self.assertEqual(AIEvaluationRun.objects.count(), 1)

    def test_prompt_versions_are_visible_to_editors(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.get('/articles/api/v2/assistant/prompts/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['version'], 'editorial-v2')
