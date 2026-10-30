from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser, Workspace, WorkspaceMembership
from ..models import AIInsight, Article


class NewsroomIntelligenceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='intel-editor', email='intel-editor@example.com', password='StrongPass123!', role='Editor')
        self.workspace = Workspace.objects.create(name='Intelligence Newsroom', slug='intelligence-newsroom', owner=self.editor, plan='team', seat_limit=10)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.editor, role='owner')
        self.article = Article.objects.create(title='A valid article title', content='Climate policy brings new jobs and community investment this year.', author=self.editor, email=self.editor.email, category='news', tags='climate jobs', agreed_to_terms=True, workspace=self.workspace)
        Article.objects.create(title='Another climate article', content='The climate policy creates jobs and community investment across the city.', author=self.editor, email=self.editor.email, category='news', tags='climate jobs', agreed_to_terms=True, workspace=self.workspace)

    def test_article_intelligence_returns_recommendations_and_duplicate_risk(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/intelligence/', format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['payload']['recommendations'])
        self.assertIn(response.data['payload']['duplicate_risk'], {'medium', 'high'})
        self.assertEqual(AIInsight.objects.count(), 1)

    def test_workspace_intelligence_returns_clusters_and_trends(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.get('/articles/api/v2/assistant/intelligence/?workspace=intelligence-newsroom')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['intelligence']['topic_clusters'])
        self.assertTrue(response.data['intelligence']['trend_terms'])
