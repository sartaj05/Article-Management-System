from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, ArticleEngagementEvent, ArticleView


class ContentPerformanceTests(TestCase):
    def test_analytics_reports_completion_and_author_comparison(self):
        author = CustomUser.objects.create_user(username='performance-author', email='performance@example.com', password='StrongPass123!', role='Journalist')
        reader = CustomUser.objects.create_user(username='performance-reader', email='reader-performance@example.com', password='StrongPass123!', role='Journalist')
        article = Article.objects.create(title='Performance story', content='Content', author=author, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        ArticleView.objects.create(article=article, user=reader)
        ArticleEngagementEvent.objects.create(article=article, user=reader, event_type='read_start')
        ArticleEngagementEvent.objects.create(article=article, user=reader, event_type='read_complete')
        client = APIClient()
        client.force_authenticate(user=author)
        response = client.get('/articles/api/v2/analytics/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_read_starts'], 1)
        self.assertEqual(response.data['read_completion_rate'], 100.0)
        self.assertEqual(response.data['top_authors'][0]['completion_rate'], 100.0)
