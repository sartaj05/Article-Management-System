from rest_framework.test import APITestCase


class HealthCheckTests(APITestCase):
    def test_health_endpoint_reports_database_status(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'status': 'healthy', 'database': 'ok'})
