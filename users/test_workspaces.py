from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomUser, WorkspaceMembership


class WorkspaceFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = CustomUser.objects.create_user(
            username='workspace-owner', email='owner@example.com', password='StrongPass123!', role='Editor',
        )
        self.member = CustomUser.objects.create_user(
            username='workspace-writer', email='writer@example.com', password='StrongPass123!', role='Journalist',
        )
        self.client.force_authenticate(self.owner)

    def test_owner_can_create_workspace_and_invite_member(self):
        response = self.client.post('/api/workspaces/', {'name': 'Daily Newsroom', 'description': 'Editorial team'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['slug'], 'daily-newsroom')

        response = self.client.post('/api/workspaces/daily-newsroom/invite/', {'email': self.member.email, 'role': 'writer'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['role'], 'writer')
        self.invitation_token = response.data['token']

        self.client.force_authenticate(self.member)
        response = self.client.post(f'/api/workspaces/invitations/{self.invitation_token}/accept/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(WorkspaceMembership.objects.filter(workspace__slug='daily-newsroom', user=self.member).exists())

    def test_non_member_cannot_read_workspace_members(self):
        self.client.post('/api/workspaces/', {'name': 'Private Desk'}, format='json')
        outsider = CustomUser.objects.create_user(
            username='workspace-outsider', email='outsider@example.com', password='StrongPass123!', role='Journalist',
        )
        self.client.force_authenticate(outsider)
        response = self.client.get('/api/workspaces/private-desk/members/')
        self.assertEqual(response.status_code, 403)
