from rest_framework.test import APITestCase

from users.models import CustomUser
from ..models import Article, ArticleTranslation


class TranslationTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='translation-author', email='translation@example.com', password='Password123!', role='Journalist')
        self.article = Article.objects.create(title='Translation article test', content='English content', author=self.author, agreed_to_terms=True)

    def test_author_can_create_draft_translation_and_editor_can_publish(self):
        self.client.force_authenticate(self.author)
        response = self.client.post(
            f'/articles/api/v2/articles/{self.article.id}/translations/',
            {'language_code': 'hi', 'title': 'Hindi article', 'content': 'Hindi content', 'status': 'draft'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        translation = ArticleTranslation.objects.get(article=self.article, language_code='hi')
        editor = CustomUser.objects.create_user(username='translation-editor', email='translation-editor@example.com', password='Password123!', role='Editor')
        self.client.force_authenticate(editor)
        response = self.client.patch(f'/articles/api/v2/translations/{translation.id}/', {'status': 'published'}, format='json')
        self.assertEqual(response.status_code, 200)
        translation.refresh_from_db()
        self.assertEqual(translation.status, 'published')
