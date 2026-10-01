from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import CustomUser

from .models import Article, Comment, Like, Notification


class ArticleFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.journalist = CustomUser.objects.create_user(
            username='journalist-test', email='journalist-test@example.com',
            password='StrongPass123!', role='Journalist',
        )
        self.editor = CustomUser.objects.create_user(
            username='editor-test', email='editor-test@example.com',
            password='StrongPass123!', role='Editor',
        )
        self.article = Article.objects.create(
            title='A valid article title',
            content='Article content for workflow tests.',
            author=self.journalist,
            email=self.journalist.email,
            category='news',
            agreed_to_terms=True,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_complete_article_workflow(self):
        self.authenticate(self.journalist)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/submit/')
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.workflow_status, 'submitted')

        self.authenticate(self.editor)
        response = self.client.patch(
            f'/articles/api/v2/articles/{self.article.id}/review/',
            {'decision': 'approve'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.workflow_status, 'approved')

        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/publish/')
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.workflow_status, 'published')
        self.assertTrue(self.article.is_visible)

    def test_rejection_requires_reason_and_notifies_author(self):
        self.authenticate(self.journalist)
        self.client.post(f'/articles/api/v2/articles/{self.article.id}/submit/')
        self.authenticate(self.editor)
        response = self.client.patch(
            f'/articles/api/v2/articles/{self.article.id}/review/',
            {'decision': 'reject'}, format='json',
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.patch(
            f'/articles/api/v2/articles/{self.article.id}/review/',
            {'decision': 'reject', 'reason': 'Please add a source.'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Notification.objects.filter(recipient=self.journalist, notification_type='rejected').exists())
        self.assertTrue(Comment.objects.filter(article=self.article, is_editorial=True).exists())

    def test_journalist_cannot_review(self):
        self.authenticate(self.journalist)
        self.client.post(f'/articles/api/v2/articles/{self.article.id}/submit/')
        response = self.client.patch(
            f'/articles/api/v2/articles/{self.article.id}/review/',
            {'decision': 'approve'}, format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_comments_likes_and_revisions(self):
        self.authenticate(self.journalist)
        response = self.client.patch(
            f'/articles/api/v2/articles/{self.article.id}/',
            {'content': 'Updated content with a revision.'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.article.revisions.count(), 1)

        response = self.client.post(
            f'/articles/api/v2/articles/{self.article.id}/comments/',
            {'content': 'Useful draft feedback.'}, format='json',
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/like/')
        self.assertTrue(response.data['liked'])
        self.assertEqual(Like.objects.filter(article=self.article, user=self.journalist).count(), 1)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/like/')
        self.assertFalse(response.data['liked'])

    def test_search_pagination_and_analytics(self):
        self.authenticate(self.journalist)
        self.article.workflow_status = 'published'
        self.article.status = 'published'
        self.article.is_visible = True
        self.article.save(update_fields=['workflow_status', 'status', 'is_visible'])
        response = self.client.get('/articles/api/v2/articles/search/?q=valid&workflow_status=published')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        response = self.client.get('/articles/api/v2/analytics/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['published'], 1)

    def test_public_distribution_endpoints(self):
        self.article.workflow_status = 'published'
        self.article.status = 'published'
        self.article.is_visible = True
        self.article.published_at = timezone.now()
        self.article.save(update_fields=['workflow_status', 'status', 'is_visible', 'published_at'])
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f'/articles/read/{self.article.slug}/').status_code, 200)
        self.assertEqual(self.client.get('/sitemap.xml').status_code, 200)
        self.assertEqual(self.client.get('/rss.xml').status_code, 200)
        self.assertEqual(self.client.get('/robots.txt').status_code, 200)
