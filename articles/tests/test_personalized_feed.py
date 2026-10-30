from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser, ReaderInterest
from ..models import Article, ArticleEngagementEvent, ArticleView, ReadingProgress


class PersonalizedFeedTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.reader = CustomUser.objects.create_user(username='feed-reader', email='feed-reader@example.com', password='StrongPass123!', role='Journalist')
        self.author = CustomUser.objects.create_user(username='feed-author', email='feed-author@example.com', password='StrongPass123!', role='Journalist')
        self.latest = Article.objects.create(title='Latest feed article', content='Content', author=self.author, category='news', agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        self.popular = Article.objects.create(title='Popular feed article', content='Content', author=self.author, category='opinion', agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        ArticleView.objects.create(article=self.popular, user=self.reader)
        self.client.force_authenticate(self.reader)

    def test_cold_start_feed_returns_explainable_latest_recommendations(self):
        response = self.client.get('/articles/api/v2/feed/for-you/?limit=1')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['cold_start'])
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('recommendation_reason', response.data['results'][0])

    def test_interest_and_mode_are_supported(self):
        ReaderInterest.objects.create(user=self.reader, interest_type='category', value='opinion')
        response = self.client.get('/articles/api/v2/feed/for-you/?mode=trending&limit=10')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mode'], 'trending')
        self.assertFalse(response.data['cold_start'])

    def test_reader_insights_returns_streak_resume_and_topics(self):
        ReaderInterest.objects.create(user=self.reader, interest_type='tag', value='climate')
        ArticleEngagementEvent.objects.create(article=self.popular, user=self.reader, event_type='read_complete')
        ReadingProgress.objects.create(article=self.latest, user=self.reader, progress_percent=42)
        response = self.client.get('/articles/api/v2/reader/insights/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['streak']['current'], 1)
        self.assertEqual(response.data['completed_articles'], 1)
        self.assertEqual(response.data['resume_reading'][0]['progress_percent'], 42)
        self.assertEqual(response.data['recommendation_topics'][0]['value'], 'climate')
