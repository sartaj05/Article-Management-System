from rest_framework.test import APITestCase

from users.models import CustomUser
from ..permissions import capabilities_for_user, user_has_capability


class CapabilityTests(APITestCase):
    def setUp(self):
        self.journalist = CustomUser.objects.create_user(
            username='cap-journalist', email='cap-journalist@example.com',
            password='Password123!', role='Journalist',
        )
        self.editor = CustomUser.objects.create_user(
            username='cap-editor', email='cap-editor@example.com',
            password='Password123!', role='Editor',
        )
        self.admin = CustomUser.objects.create_user(
            username='cap-admin', email='cap-admin@example.com',
            password='Password123!', role='Admin',
        )

    def test_capability_policy_is_role_specific(self):
        self.assertTrue(user_has_capability(self.journalist, 'article.submit'))
        self.assertFalse(user_has_capability(self.journalist, 'article.publish'))
        self.assertTrue(user_has_capability(self.editor, 'article.review'))
        self.assertTrue(user_has_capability(self.admin, 'system.health.view'))

    def test_authenticated_user_can_read_capabilities(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get('/articles/api/v2/permissions/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['role'], 'Editor')
        self.assertIn('article.review', response.data['capabilities'])

    def test_anonymous_user_cannot_read_capabilities(self):
        response = self.client.get('/articles/api/v2/permissions/me/')
        self.assertEqual(response.status_code, 401)
