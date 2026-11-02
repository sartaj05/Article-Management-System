from django.test import TestCase


class OpenAPIDocumentationTests(TestCase):
    def test_openapi_json_alias_is_available(self):
        response = self.client.get('/api/openapi.json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Article Studio API', response.content.decode())

    def test_interactive_api_docs_are_available(self):
        response = self.client.get('/api/docs/')
        self.assertEqual(response.status_code, 200)
