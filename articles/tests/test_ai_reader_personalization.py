from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser, PersonalizationPreference, ReaderInterest
from ..models import AIReaderRecommendation, Article


class AIReaderPersonalizationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.reader = CustomUser.objects.create_user(username='ai-reader', email='ai-reader@example.com', password='StrongPass123!', role='Journalist')
        PersonalizationPreference.objects.create(user=self.reader, enabled=True)
        ReaderInterest.objects.create(user=self.reader, interest_type='category', value='news')
        self.article = Article.objects.create(title='A valid article title', content='News about city policy and community investment.', author=self.reader, email=self.reader.email, category='news', tags='policy', agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        Article.objects.create(title='Opinion article title', content='An opinion about culture and art.', author=self.reader, email=self.reader.email, category='opinion', agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)

    def test_ai_feed_returns_explainable_recommendations(self):
        self.client.force_authenticate(user=self.reader)
        response = self.client.get('/articles/api/v2/feed/ai-for-you/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mode'], 'ai_for_you')
        self.assertTrue(response.data['results'])
        self.assertTrue(response.data['results'][0]['recommendation_reason'])
        self.assertTrue(AIReaderRecommendation.objects.exists())

    def test_ai_digest_returns_newsletter_selection(self):
        self.client.force_authenticate(user=self.reader)
        response = self.client.get('/articles/api/v2/reader/ai-digest/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['subject'], 'Your personalized reading list')
        self.assertTrue(response.data['articles'])
