from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import CustomUser, Workspace, WorkspaceMembership
from ..models import AIUsageEvent, AIWorkspacePolicy, Article


class AIGovernanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='policy-editor', email='policy-editor@example.com', password='StrongPass123!', role='Editor')
        self.workspace = Workspace.objects.create(name='AI Policy Newsroom', slug='ai-policy-newsroom', owner=self.editor, plan='team', seat_limit=10)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.editor, role='owner')
        self.article = Article.objects.create(title='A valid article title', content='Contact editor@example.com for details about the article.', author=self.editor, email=self.editor.email, category='news', agreed_to_terms=True, workspace=self.workspace)

    @override_settings(AI_ASSISTANT_COST_PER_1K_TOKENS=0.25)
    def test_policy_redacts_pii_and_records_usage(self):
        AIWorkspacePolicy.objects.create(workspace=self.workspace, max_input_chars=40, redact_pii=True)
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/assistant/', {'action': 'summarize'}, format='json')
        self.assertEqual(response.status_code, 200)
        usage = AIUsageEvent.objects.get()
        self.assertTrue(usage.redacted_pii)
        self.assertGreater(usage.total_tokens, 0)
        self.assertGreaterEqual(float(usage.estimated_cost), 0)

    def test_policy_blocks_disallowed_action(self):
        AIWorkspacePolicy.objects.create(workspace=self.workspace, allowed_actions=['seo'])
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/assistant/', {'action': 'summarize'}, format='json')
        self.assertEqual(response.status_code, 429)

    def test_editor_can_read_workspace_usage(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.get('/articles/api/v2/assistant/governance/usage/?workspace=ai-policy-newsroom')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['event_count'], 0)
