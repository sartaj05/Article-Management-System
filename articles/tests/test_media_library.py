from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, ArticleAsset


class MediaLibraryFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='media-editor', email='media-editor@example.com', password='StrongPass123!', role='Editor',
        )
        self.article = Article.objects.create(
            title='Media library article', content='Article content', author=self.user,
            author_name=self.user.username, email=self.user.email, agreed_to_terms=True,
        )
        self.client.force_authenticate(self.user)

    def test_editor_can_upload_and_attach_media_asset(self):
        upload = SimpleUploadedFile('cover.jpg', b'fake-image-bytes', content_type='image/jpeg')
        response = self.client.post('/articles/api/v2/media-library/', {
            'title': 'Cover photo', 'media_type': 'image', 'file': upload,
            'alt_text': 'A newsroom desk', 'credit': 'Article Studio', 'license': 'owned',
        }, format='multipart')
        self.assertEqual(response.status_code, 201)
        asset_id = response.data['id']

        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/assets/', {
            'asset_id': asset_id, 'role': 'hero', 'position': 0,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(ArticleAsset.objects.filter(article=self.article, asset_id=asset_id, role='hero').exists())

        response = self.client.get('/articles/api/v2/media-library/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['alt_text'], 'A newsroom desk')

    def test_duplicate_upload_returns_conflict_and_search_filters_assets(self):
        payload = {
            'title': 'Searchable photo', 'media_type': 'image',
            'alt_text': 'Newsroom desk', 'credit': 'Article Studio', 'license': 'owned',
        }
        first = self.client.post('/articles/api/v2/media-library/', {
            **payload, 'file': SimpleUploadedFile('desk.jpg', b'unique-image', content_type='image/jpeg'),
        }, format='multipart')
        self.assertEqual(first.status_code, 201)
        self.assertTrue(first.data['file_hash'])

        duplicate = self.client.post('/articles/api/v2/media-library/', {
            **payload, 'file': SimpleUploadedFile('copy.jpg', b'unique-image', content_type='image/jpeg'),
        }, format='multipart')
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.data['duplicate_asset_id'], first.data['id'])

        response = self.client.get('/articles/api/v2/media-library/?q=searchable')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
