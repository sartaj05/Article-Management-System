from rest_framework.test import APITestCase


class HealthCheckTests(APITestCase):
    def test_health_endpoint_reports_database_status(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'status': 'healthy', 'database': 'ok'})

    def test_verbose_health_endpoint_includes_checks_and_request_id(self):
        response = self.client.get('/health/?verbose=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['checks']['database'], 'ok')
        self.assertTrue(response.data['request_id'])
        self.assertEqual(response.headers['X-Request-ID'], response.data['request_id'])
