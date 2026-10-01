import base64

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from users.models import CustomUser
from .models import Article, ArticleImage


class ImageGalleryTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='gallery-author', email='gallery@example.com', password='Password123!', role='Journalist')
        self.article = Article.objects.create(title='Gallery article test', content='Content', author=self.author, agreed_to_terms=True)

    def test_author_can_upload_list_and_delete_gallery_image(self):
        self.client.force_authenticate(self.author)
        upload = SimpleUploadedFile(
            'cover.png',
            base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='),
            content_type='image/png',
        )
        response = self.client.post(
            f'/articles/api/v2/articles/{self.article.id}/gallery/',
            {'image': upload, 'caption': 'Cover image', 'sort_order': 1},
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)
        image = ArticleImage.objects.get(article=self.article)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/gallery/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        response = self.client.delete(f'/articles/api/v2/gallery/images/{image.id}/')
        self.assertEqual(response.status_code, 204)
