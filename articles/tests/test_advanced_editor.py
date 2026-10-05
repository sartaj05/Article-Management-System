from rest_framework.test import APITestCase

from users.models import CustomUser
from ..models import Article, ArticleAutosave


class AdvancedEditorTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='editor-author', email='editor-author@example.com', password='Password123!', role='Journalist')
        self.article = Article.objects.create(title='Advanced editor test', content='Initial content', author=self.author, agreed_to_terms=True)

    def test_author_can_autosave_rich_editor_state(self):
        self.client.force_authenticate(self.author)
        response = self.client.put(
            f'/articles/api/v2/articles/{self.article.id}/autosave/',
            {'title': 'Advanced editor test', 'content': '<p>Draft content</p>', 'content_format': 'html', 'editor_state': {'cursor': 12}},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        autosave = ArticleAutosave.objects.get(article=self.article)
        self.assertEqual(autosave.content_format, 'html')
        self.assertEqual(autosave.editor_state['cursor'], 12)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/autosave/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['content'], '<p>Draft content</p>')

    def test_author_can_run_accessibility_quality_checks(self):
        self.article.content_format = 'html'
        self.article.content = '<h1>Title</h1><h3>Skipped heading</h3><img src="cover.jpg">'
        self.article.save(update_fields=['content_format', 'content'])
        self.client.force_authenticate(self.author)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/accessibility/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['passed'])
        self.assertGreaterEqual(response.data['errors'], 1)
        self.assertTrue(any(issue['code'] == 'missing_image_alt' for issue in response.data['issues']))
