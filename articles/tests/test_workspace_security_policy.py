from django.test import TestCase
from rest_framework.test import APIClient

from articles.models import Article, WorkspaceApprovalPolicy
from users.models import CustomUser, Workspace, WorkspaceMembership


class WorkspaceSecurityPolicyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.reviewer = CustomUser.objects.create_user(username='policy-reviewer', email='reviewer@example.com', password='StrongPass123!', role='Editor')
        self.publisher = CustomUser.objects.create_user(username='policy-publisher', email='publisher@example.com', password='StrongPass123!', role='Editor')
        self.workspace = Workspace.objects.create(name='Policy newsroom', slug='policy-newsroom', owner=self.reviewer)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.reviewer, role='owner')
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.publisher, role='editor')
        self.article = Article.objects.create(
            title='Policy newsroom article', content='Content', author=self.reviewer,
            workspace=self.workspace, workflow_status='approved', review_status='approved',
            agreed_to_terms=True, reviewed_by=self.reviewer,
        )
        WorkspaceApprovalPolicy.objects.create(workspace=self.workspace, require_dual_publish=True)

    def test_security_policy_is_workspace_scoped_and_requires_different_publisher(self):
        self.client.force_authenticate(self.reviewer)
        policy = self.client.get('/articles/api/v2/security/workspace-policy/', HTTP_X_WORKSPACE_SLUG=self.workspace.slug)
        self.assertEqual(policy.status_code, 200)
        blocked = self.client.post(f'/articles/api/v2/articles/{self.article.id}/publish/', HTTP_X_WORKSPACE_SLUG=self.workspace.slug)
        self.assertEqual(blocked.status_code, 409)

        self.client.force_authenticate(self.publisher)
        published = self.client.post(f'/articles/api/v2/articles/{self.article.id}/publish/', HTTP_X_WORKSPACE_SLUG=self.workspace.slug)
        self.assertEqual(published.status_code, 200)

    def test_workspace_permission_override_can_disable_publish(self):
        self.client.force_authenticate(self.reviewer)
        response = self.client.patch(
            '/articles/api/v2/security/workspace-policy/',
            {'permissions': [{'role': 'Editor', 'capability': 'article.publish', 'is_enabled': False}]},
            format='json', HTTP_X_WORKSPACE_SLUG=self.workspace.slug,
        )
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.publisher)
        blocked = self.client.post(f'/articles/api/v2/articles/{self.article.id}/publish/', HTTP_X_WORKSPACE_SLUG=self.workspace.slug)
        self.assertEqual(blocked.status_code, 403)
