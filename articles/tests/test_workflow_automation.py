from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser, Workspace, WorkspaceMembership
from ..models import Article, ArticleAssignment, WorkflowRule


class WorkflowAutomationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = CustomUser.objects.create_user(username='automation-author', email='automation-author@example.com', password='StrongPass123!', role='Journalist')
        self.editor = CustomUser.objects.create_user(username='automation-editor', email='automation-editor@example.com', password='StrongPass123!', role='Editor')
        self.workspace = Workspace.objects.create(name='Automation desk', slug='automation-desk', owner=self.editor)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.editor, role='owner')
        self.article = Article.objects.create(title='Automation workflow story', content='A sufficiently detailed story body.', author=self.author, agreed_to_terms=True, workspace=self.workspace)

    def test_submission_rule_auto_assigns_least_loaded_editor(self):
        WorkflowRule.objects.create(workspace=self.workspace, name='Auto assign review', from_status='draft', to_status='submitted', auto_assign_role='Editor')
        self.client.force_authenticate(self.author)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/submit/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ArticleAssignment.objects.filter(article=self.article, editor=self.editor).exists())

    def test_approval_rule_requires_sources(self):
        WorkflowRule.objects.create(workspace=self.workspace, name='Source gate', from_status='submitted', to_status='approved', require_sources=True)
        self.article.workflow_status = 'submitted'
        self.article.save(update_fields=['workflow_status'])
        self.client.force_authenticate(self.editor)
        response = self.client.patch(f'/articles/api/v2/articles/{self.article.id}/review/', {'decision': 'approve'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Source gate', response.data['rules'][0])
