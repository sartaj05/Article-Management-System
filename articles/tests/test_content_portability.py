from io import BytesIO
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article


class ContentPortabilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='portability-user', email='portability@example.com', password='StrongPass123!', role='Journalist')
        self.article = Article.objects.create(title='Portable article title', content='Portable article body.', author=self.user, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        self.client.force_authenticate(self.user)

    def test_article_can_export_markdown_and_docx(self):
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/export/?export_format=markdown')
        self.assertEqual(response.status_code, 200)
        self.assertIn('# Portable article title', response.content.decode())
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/export/?export_format=docx')
        self.assertEqual(response.status_code, 200)
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertIn('word/document.xml', archive.namelist())

    def test_markdown_file_can_create_draft_article(self):
        upload = SimpleUploadedFile('imported-story.md', b'# Imported story\n\nImported content.', content_type='text/markdown')
        response = self.client.post('/articles/api/v2/import/', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)
        imported = Article.objects.get(pk=response.data['id'])
        self.assertEqual(imported.content_format, 'markdown')
        self.assertIn('Imported content', imported.content)
