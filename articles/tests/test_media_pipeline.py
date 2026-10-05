from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, ArticleMedia


class MediaPipelineTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = CustomUser.objects.create_user(username='media-author', email='media-author@example.com', password='StrongPass123!', role='Journalist')
        self.article = Article.objects.create(title='Media pipeline article', content='Content', author=self.author, agreed_to_terms=True)
        self.client.force_authenticate(self.author)

    def test_media_can_be_processed_with_metadata(self):
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/media/', {
            'media_type': 'audio', 'title': 'Interview audio', 'file': SimpleUploadedFile('interview.mp3', b'audio-bytes', content_type='audio/mpeg'),
        }, format='multipart')
        self.assertEqual(response.status_code, 201)
        media_id = response.data['id']
        response = self.client.post(f'/articles/api/v2/media/{media_id}/process/')
        self.assertEqual(response.status_code, 200)
        media = ArticleMedia.objects.get(pk=media_id)
        self.assertEqual(media.processing_status, 'ready')
        self.assertGreater(media.file_size, 0)
        self.assertEqual(media.mime_type, 'audio/mpeg')
