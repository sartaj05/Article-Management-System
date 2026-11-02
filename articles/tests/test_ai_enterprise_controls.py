from django.test import TestCase
from rest_framework.test import APIClient

from articles.models import AIWorkspacePolicy, Article
from users.models import CustomUser, Workspace, WorkspaceMembership


class AIEnterpriseControlsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='ai-enterprise-editor', email='ai-enterprise@example.com', password='StrongPass123!', role='Editor')
        self.workspace = Workspace.objects.create(name='AI Enterprise newsroom', slug='ai-enterprise-newsroom', owner=self.editor)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.editor, role='owner')
        self.article = Article.objects.create(title='AI enterprise article', content='A safe article body.', author=self.editor, workspace=self.workspace, agreed_to_terms=True)
        self.client.force_authenticate(self.editor)

    def test_policy_exposes_enterprise_controls_and_blocks_disallowed_provider(self):
        response = self.client.patch(
            '/articles/api/v2/assistant/governance/policy/',
            {'workspace_slug': self.workspace.slug, 'allowed_providers': ['openai'], 'allowed_models': ['gpt-enterprise'], 'data_retention_days': 7, 'training_data_opt_out': True, 'approved_prompt_version': 'approved-v2'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data_retention_days'], 7)
        blocked = self.client.post(f'/articles/api/v2/articles/{self.article.id}/assistant/', {'action': 'summarize'}, format='json')
        self.assertEqual(blocked.status_code, 429)
        policy = AIWorkspacePolicy.objects.get(workspace=self.workspace)
        self.assertTrue(policy.training_data_opt_out)
