from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, Comment, CommentReport


class CommentModerationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = CustomUser.objects.create_user(username='comment-author', email='comment-author@example.com', password='StrongPass123!', role='Journalist')
        self.reader = CustomUser.objects.create_user(username='comment-reader', email='comment-reader@example.com', password='StrongPass123!', role='Journalist')
        self.editor = CustomUser.objects.create_user(username='comment-editor', email='comment-editor@example.com', password='StrongPass123!', role='Editor')
        self.article = Article.objects.create(title='Comment moderation article', content='Content', author=self.author, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)

    def test_risky_comment_enters_pending_state_and_can_be_reported(self):
        self.client.force_authenticate(self.reader)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/comments/', {'content': 'Buy now for guaranteed profit'}, format='json')
        self.assertEqual(response.status_code, 201)
        comment = Comment.objects.get()
        self.assertEqual(comment.moderation_status, 'pending')
        response = self.client.post(f'/articles/api/v2/comments/{comment.id}/report/', {'reason': 'Promotional spam'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(CommentReport.objects.filter(comment=comment).exists())

    def test_editor_can_resolve_comment_report(self):
        comment = Comment.objects.create(article=self.article, author=self.reader, content='Needs review')
        report = CommentReport.objects.create(comment=comment, reported_by=self.author, reason='Abuse')
        self.client.force_authenticate(self.editor)
        response = self.client.patch(f'/articles/api/v2/comment-moderation/{report.id}/', {'decision': 'hide', 'resolution': 'Hidden after review.'}, format='json')
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertEqual(comment.moderation_status, 'hidden')
        self.assertEqual(response.data['status'], 'reviewed')
