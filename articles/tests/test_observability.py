from django.test import SimpleTestCase, override_settings


class ObservabilityTests(SimpleTestCase):
    @override_settings(METRICS_TOKEN='test-token')
    def test_metrics_requires_token(self):
        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 404)
        response = self.client.get('/metrics/', HTTP_X_METRICS_TOKEN='test-token')
        self.assertEqual(response.status_code, 200)

    def test_security_headers_are_present(self):
        response = self.client.get('/health/')
        self.assertIn('Content-Security-Policy', response)
        self.assertIn('Permissions-Policy', response)
