from django.core.cache import cache
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article


class PublicFeedPerformanceTests(TestCase):
    def setUp(self):
        cache.clear()
        author = CustomUser.objects.create_user(username='feed-author', email='feed@example.com', password='StrongPass123!', role='Journalist')
        Article.objects.create(
            title='Cached public story', content='A published story for the public feed.', author=author,
            author_name=author.username, email=author.email, agreed_to_terms=True,
            workflow_status='published', is_visible=True,
        )
        self.client = APIClient()

    def test_anonymous_feed_uses_short_cache(self):
        first = self.client.get('/articles/api/v2/public/articles/?limit=1')
        second = self.client.get('/articles/api/v2/public/articles/?limit=1')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first['X-Cache'], 'MISS')
        self.assertEqual(second['X-Cache'], 'HIT')
        self.assertEqual(first.data, second.data)

    def test_public_feed_has_anonymous_rate_limit(self):
        with patch('articles.throttling.PublicFeedThrottle.get_rate', return_value='1/min'):
            first = self.client.get('/articles/api/v2/public/articles/?q=rate-limit-one')
            second = self.client.get('/articles/api/v2/public/articles/?q=rate-limit-two')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
