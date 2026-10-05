from rest_framework.test import APITestCase

from users.models import CustomUser
from ..models import Article, ArticleAssignment


class AdvancedPermissionTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='permission-author', email='permission-author@example.com', password='Password123!', role='Journalist')
        self.admin = CustomUser.objects.create_user(username='permission-admin', email='permission-admin@example.com', password='Password123!', role='Admin')
        self.assigned = CustomUser.objects.create_user(username='assigned-editor', email='assigned-editor@example.com', password='Password123!', role='Editor')
        self.other = CustomUser.objects.create_user(username='other-editor', email='other-editor@example.com', password='Password123!', role='Editor')
        self.article = Article.objects.create(title='Permission article test', content='Content', author=self.author, agreed_to_terms=True, workflow_status='submitted')

    def test_assignment_limits_review_access(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/assignments/', {'editor': self.assigned.id, 'can_review': True}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.other)
        response = self.client.patch(f'/articles/api/v2/articles/{self.article.id}/review/', {'decision': 'approve'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.client.force_authenticate(self.assigned)
        response = self.client.patch(f'/articles/api/v2/articles/{self.article.id}/review/', {'decision': 'approve'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ArticleAssignment.objects.filter(article=self.article, editor=self.assigned).exists())
