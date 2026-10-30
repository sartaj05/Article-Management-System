from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import CustomUser, Workspace


@override_settings(DEMO_MODE_ENABLED=True)
class DemoModeTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_demo_launcher_lists_personas_and_features(self):
        response = self.client.get('/demo/api/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['workspace'], 'Demo Newsroom')
        self.assertEqual({item['key'] for item in response.data['personas']}, {'journalist', 'editor', 'admin'})
        self.assertIn('Reader personalization', response.data['features'])

    def test_demo_login_and_reset_refresh_the_workspace(self):
        reset = self.client.post('/demo/api/', {'action': 'reset'}, format='json')
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(Workspace.objects.filter(slug='demo-newsroom').exists())
        login = self.client.post('/demo/api/', {'persona': 'editor'}, format='json')
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.data['dashboard_url'], '/editor/dashboard/')
        self.assertEqual(login.data['username'], 'demo_editor')
        self.assertEqual(self.client.session.get('_auth_user_id'), str(CustomUser.objects.get(username='demo_editor').id))

    def test_invalid_persona_is_rejected(self):
        response = self.client.post('/demo/api/', {'persona': 'unknown'}, format='json')
        self.assertEqual(response.status_code, 400)
