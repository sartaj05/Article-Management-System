from rest_framework.test import APITestCase

from users.models import CustomUser
from ..models import Article


class WorkflowPresentationTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(
            username='workflow-author', email='workflow-author@example.com',
            password='Password123!', role='Journalist',
        )
        self.editor = CustomUser.objects.create_user(
            username='workflow-editor', email='workflow-editor@example.com',
            password='Password123!', role='Editor',
        )
        self.article = Article.objects.create(
            title='Workflow presentation test', content='Content', author=self.author,
            agreed_to_terms=True, workflow_status='submitted',
        )

    def test_article_detail_exposes_progress_and_role_actions(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['available_actions'], ['review'])
        self.assertEqual(response.data['workflow_steps'][1]['state'], 'current')

    def test_rejected_article_exposes_resubmission_action_to_author(self):
        self.article.workflow_status = 'rejected'
        self.article.rejection_reason = 'Please add a source.'
        self.article.save(update_fields=['workflow_status', 'rejection_reason'])
        self.client.force_authenticate(self.author)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['available_actions'], ['submit'])
        self.assertEqual(response.data['workflow_steps'][1]['state'], 'rejected')
