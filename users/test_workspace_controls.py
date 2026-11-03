from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomUser, Workspace, WorkspaceMembership
from articles.models import Article


class WorkspaceControlsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = CustomUser.objects.create_user(username='controls-owner', email='controls-owner@example.com', password='StrongPass123!', role='Editor')
        self.member = CustomUser.objects.create_user(username='controls-member', email='controls-member@example.com', password='StrongPass123!', role='Journalist')
        self.outsider = CustomUser.objects.create_user(username='controls-outsider', email='controls-outsider@example.com', password='StrongPass123!', role='Journalist')
        self.workspace = Workspace.objects.create(name='Controls newsroom', slug='controls-newsroom', owner=self.owner, plan='team', seat_limit=10)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.owner, role='owner')
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.member, role='writer')
        Article.objects.create(title='Scoped newsroom article', content='Content', author=self.member, workspace=self.workspace, agreed_to_terms=True)

    def test_member_can_read_workspace_controls_and_quota(self):
        self.client.force_authenticate(self.member)
        response = self.client.get('/api/workspaces/controls-newsroom/controls/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['membership']['role'], 'writer')
        self.assertEqual(response.data['quotas']['articles']['used'], 1)
        self.assertEqual(response.data['analytics_scope']['workspace_slug'], 'controls-newsroom')
        onboarding = response.data['onboarding']
        self.assertEqual(onboarding['total'], 5)
        self.assertEqual(onboarding['completed'], 2)
        self.assertEqual({item['key'] for item in onboarding['items']}, {
            'workspace_profile', 'invite_team', 'create_story', 'configure_brand', 'connect_integration',
        })

    def test_non_member_cannot_read_workspace_scoped_analytics(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.get('/articles/api/v2/analytics/?workspace=controls-newsroom')
        self.assertEqual(response.status_code, 403)

    def test_owner_can_update_workspace_branding(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch('/api/workspaces/controls-newsroom/settings/', {
            'name': 'Northstar Desk',
            'description': 'A focused local newsroom',
            'logo_url': 'https://example.com/logo.svg',
            'primary_color': '#4455aa',
            'accent_color': '#ee8866',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.name, 'Northstar Desk')
        self.assertEqual(self.workspace.primary_color, '#4455aa')
        self.assertEqual(response.data['logo_url'], 'https://example.com/logo.svg')

    def test_regular_member_cannot_update_workspace_branding(self):
        self.client.force_authenticate(self.member)
        response = self.client.patch('/api/workspaces/controls-newsroom/settings/', {'name': 'Not allowed'}, format='json')
        self.assertEqual(response.status_code, 403)
