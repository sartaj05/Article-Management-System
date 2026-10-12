from rest_framework.test import APITestCase

from users.models import CustomUser
from ..audit import record_audit_event
from ..models import Article


class WorkflowTimelineTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(
            username='timeline-author', email='timeline-author@example.com',
            password='Password123!', role='Journalist',
        )
        self.editor = CustomUser.objects.create_user(
            username='timeline-editor', email='timeline-editor@example.com',
            password='Password123!', role='Editor',
        )
        self.article = Article.objects.create(
            title='Workflow timeline article', content='Timeline content',
            author=self.author, agreed_to_terms=True, workflow_status='submitted',
            rejection_reason='Please add a source.',
        )
        record_audit_event(actor=self.author, action='article_submitted', article=self.article)

    def test_author_can_read_timeline_with_steps_and_events(self):
        self.client.force_authenticate(self.author)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/timeline/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['workflow_status'], 'submitted')
        self.assertEqual(response.data['rejection_reason'], 'Please add a source.')
        self.assertEqual(response.data['events'][0]['action'], 'article_submitted')
        self.assertEqual(response.data['workflow_steps'][1]['state'], 'current')

    def test_other_journalist_cannot_read_timeline(self):
        other = CustomUser.objects.create_user(
            username='timeline-other', email='timeline-other@example.com',
            password='Password123!', role='Journalist',
        )
        self.client.force_authenticate(other)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/timeline/')
        self.assertEqual(response.status_code, 403)
