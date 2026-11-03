from django.test import TestCase

from .models import CustomUser, SSOProvider, Workspace, WorkspaceMembership


class SecurityCenterPageTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='security-center-admin',
            email='security-center-admin@example.com',
            password='StrongPass123!',
            role='Admin',
        )
        self.editor = CustomUser.objects.create_user(
            username='security-center-editor',
            email='security-center-editor@example.com',
            password='StrongPass123!',
            role='Editor',
        )
        self.workspace = Workspace.objects.create(name='Security newsroom', slug='security-newsroom', owner=self.admin)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.admin, role='owner')

    def test_security_center_is_available_to_authenticated_users(self):
        self.client.force_login(self.editor)
        response = self.client.get('/account/security/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Security &amp; identity')
        self.assertContains(response, 'API keys')
        self.assertNotContains(response, 'SSO providers')

    def test_admin_security_center_includes_identity_administration(self):
        self.client.force_login(self.admin)
        response = self.client.get('/account/security/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SSO providers')
        self.assertContains(response, 'SCIM directory access')

    def test_sso_update_keeps_existing_secret_when_form_omits_it(self):
        self.client.force_login(self.admin)
        SSOProvider.objects.create(provider='oidc', client_id='old-client', client_secret='keep-this-secret')
        response = self.client.patch('/sso/providers/', {
            'provider': 'oidc',
            'client_id': 'new-client',
            'is_enabled': True,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        provider = SSOProvider.objects.get(provider='oidc')
        self.assertEqual(provider.client_id, 'new-client')
        self.assertEqual(provider.client_secret, 'keep-this-secret')
