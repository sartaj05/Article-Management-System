from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import AIFeedback, Article, EditorialAssistantRun


class AIFeedbackTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='feedback-editor', email='feedback-editor@example.com', password='StrongPass123!', role='Editor')
        self.article = Article.objects.create(title='A valid article title', content='Feedback article content.', author=self.editor, email=self.editor.email, category='news', agreed_to_terms=True)
        self.run = EditorialAssistantRun.objects.create(article=self.article, requested_by=self.editor, action='summarize', provider='local-rule-based', suggestions={'summary': 'Generated summary'})

    def test_editor_can_record_corrected_feedback(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(f'/articles/api/v2/assistant/runs/{self.run.id}/feedback/', {'feedback_type': 'corrected', 'field': 'summary', 'corrected_value': 'Improved summary', 'note': 'Added the missing context.'}, format='json')
        self.assertEqual(response.status_code, 201)
        feedback = AIFeedback.objects.get()
        self.assertEqual(feedback.original_value, 'Generated summary')
        self.assertEqual(feedback.corrected_value, 'Improved summary')

    def test_feedback_summary_counts_actions(self):
        AIFeedback.objects.create(run=self.run, article=self.article, user=self.editor, action='summarize', feedback_type='accepted')
        self.client.force_authenticate(user=self.editor)
        response = self.client.get('/articles/api/v2/assistant/feedback/summary/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['feedback'][0]['count'], 1)
