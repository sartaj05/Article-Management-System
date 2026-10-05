from rest_framework.test import APITestCase

from users.models import CustomUser
from ..models import Article, Bookmark


class BookmarkTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='bookmark-user', email='bookmark@example.com', password='Password123!', role='Journalist')
        self.article = Article.objects.create(title='Bookmark article test', content='Content', author=self.user, agreed_to_terms=True)

    def test_user_can_toggle_and_list_bookmarks(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/bookmark/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['bookmarked'])
        response = self.client.get('/articles/api/v2/bookmarks/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertTrue(Bookmark.objects.filter(user=self.user, article=self.article).exists())
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/bookmark/')
        self.assertFalse(response.data['bookmarked'])
