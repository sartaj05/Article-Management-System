from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, ArticleAssignment


class AssignmentBoardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(username='board-admin', email='board-admin@example.com', password='StrongPass123!', role='Admin')
        self.editor = CustomUser.objects.create_user(username='board-editor', email='board-editor@example.com', password='StrongPass123!', role='Editor')
        self.author = CustomUser.objects.create_user(username='board-author', email='board-author@example.com', password='StrongPass123!', role='Journalist')
        self.article = Article.objects.create(title='Assignment board article', content='Content', author=self.author, agreed_to_terms=True)

    def test_admin_can_create_and_filter_board_assignment(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/assignments/', {
            'editor': self.editor.id, 'priority': 'urgent', 'status': 'in_progress', 'notes': 'Review sources first.',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        assignment = ArticleAssignment.objects.get()
        self.assertEqual(assignment.priority, 'urgent')
        response = self.client.get('/articles/api/v2/assignments/board/?status=in_progress')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['columns']['in_progress'][0]['article_title'], self.article.title)

    def test_editor_can_move_assignment_on_board(self):
        assignment = ArticleAssignment.objects.create(article=self.article, editor=self.editor)
        self.client.force_authenticate(self.editor)
        response = self.client.patch(f'/articles/api/v2/articles/{self.article.id}/assignments/', {
            'assignment_id': assignment.id, 'status': 'review', 'priority': 'high',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'review')
