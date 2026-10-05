from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import CustomUser, MembershipPlan, MembershipSubscription

from ..models import Article, ArticlePresence, Comment, Like, Notification


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

    def test_editorial_assistant_returns_reviewable_suggestions(self):
        self.authenticate(self.journalist)
        response = self.client.post(
            f'/articles/api/v2/articles/{self.article.id}/assistant/',
            {'action': 'seo'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['requires_review'])
        self.assertEqual(response.data['provider'], 'local-rule-based')
        self.assertIn('meta_description', response.data['suggestions'])

    def test_personalized_feed_prioritizes_followed_category(self):
        from users.models import ReaderInterest
        ReaderInterest.objects.create(user=self.journalist, interest_type='category', value='news')
        self.article.workflow_status = 'published'
        self.article.status = 'published'
        self.article.is_visible = True
        self.article.save(update_fields=['workflow_status', 'status', 'is_visible'])
        self.authenticate(self.journalist)
        response = self.client.get('/articles/api/v2/feed/for-you/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['id'], self.article.id)

    def test_sources_and_fact_checks_are_visible_on_published_articles(self):
        self.article.workflow_status = 'published'
        self.article.status = 'published'
        self.article.is_visible = True
        self.article.save(update_fields=['workflow_status', 'status', 'is_visible'])
        self.authenticate(self.journalist)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/sources/', {'url': 'https://example.com/source', 'title': 'Primary source', 'source_type': 'primary'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.authenticate(self.editor)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/fact-checks/', {'claim': 'A test claim', 'verdict': 'verified', 'explanation': 'Checked against the source.'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f'/articles/api/v2/articles/{self.article.id}/sources/').status_code, 200)
        self.assertEqual(self.client.get(f'/articles/api/v2/articles/{self.article.id}/fact-checks/').status_code, 200)

    def test_collaboration_presence_heartbeat_and_leave(self):
        self.authenticate(self.journalist)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/collaboration/', {'section': 'content', 'cursor_position': 24}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ArticlePresence.objects.filter(article=self.article, user=self.journalist).exists())
        self.assertEqual(self.client.get(f'/articles/api/v2/articles/{self.article.id}/collaboration/').status_code, 200)
        response = self.client.delete(f'/articles/api/v2/articles/{self.article.id}/collaboration/')
        self.assertTrue(response.data['left'])

    def test_article_media_can_be_added_and_read_publicly(self):
        self.authenticate(self.journalist)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/media/', {'media_type': 'audio', 'title': 'Article audio', 'external_url': 'https://cdn.example.com/article.mp3'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.article.workflow_status = 'published'
        self.article.status = 'published'
        self.article.is_visible = True
        self.article.save(update_fields=['workflow_status', 'status', 'is_visible'])
        self.client.force_authenticate(user=None)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/media/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['media_type'], 'audio')

    def test_free_membership_unlocks_premium_content(self):
        self.article.is_premium = True
        self.article.workflow_status = 'published'
        self.article.status = 'published'
        self.article.is_visible = True
        self.article.save(update_fields=['is_premium', 'workflow_status', 'status', 'is_visible'])
        free_plan = MembershipPlan.objects.create(name='Community', slug='community', features=['Premium articles'])
        self.client.force_authenticate(user=self.journalist)
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/')
        self.assertEqual(response.status_code, 403)
        response = self.client.post('/api/membership/checkout/', {'plan_id': free_plan.id}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(MembershipSubscription.objects.filter(user=self.journalist, status='active').exists())
        response = self.client.get(f'/articles/api/v2/articles/{self.article.id}/')
        self.assertEqual(response.status_code, 200)
