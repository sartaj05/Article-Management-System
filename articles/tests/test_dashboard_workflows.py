from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from articles.models import Article
from users.models import CustomUser, TwoFactorAuth
from users.two_factor import generate_secret, totp


class DashboardWorkflowTests(TestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='dashboard-writer', email='writer@example.org', password='StrongPass123!', role='Journalist')
        self.other = CustomUser.objects.create_user(username='other-writer', email='other@example.org', password='StrongPass123!', role='Journalist')
        self.admin = CustomUser.objects.create_user(username='dashboard-admin', email='admin@example.org', password='StrongPass123!', role='Admin')
        self.client = APIClient(enforce_csrf_checks=True)

    def login(self, user):
        self.client.get('/login-template/')
        return self.client.post('/api/login/', {'username': user.username, 'password': 'StrongPass123!'},
                                format='json', HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)

    def test_session_can_reauthenticate_and_logout_with_csrf(self):
        self.assertEqual(self.login(self.author).status_code, 200)
        response = self.login(self.author)
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/api/logout/', {'refresh': response.data['token']['refresh']},
                                    format='json', HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/journalist/dashboard/').status_code, 302)

    def test_logout_does_not_revoke_another_users_refresh_token(self):
        self.login(self.author)
        other_token = RefreshToken.for_user(self.other)
        response = self.client.post('/api/logout/', {'refresh': str(other_token)}, format='json',
                                    HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 403)
        RefreshToken(str(other_token))  # Still valid, not blacklisted.

    def test_journalist_count_is_scoped_to_the_author(self):
        for author in (self.author, self.other):
            Article.objects.create(title=f'Story by {author.username}', content='Content', author=author)
        self.client.force_authenticate(self.author)
        self.assertEqual(self.client.get('/articles/api/articles/count/').data['article_count'], 1)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/articles/api/articles/count/').data['article_count'], 2)

    def test_browser_can_create_draft_without_optional_image_or_location(self):
        self.login(self.author)
        response = self.client.post('/articles/api/articles/create/', {
            'title': 'Dashboard draft creation', 'content': 'A story to review.', 'email': 'writer@example.org',
            'category': 'features', 'tags': 'tech,political', 'agreed_to_terms': 'true',
        }, HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['tags'], 'tech,political')
        self.assertEqual(response.data['workflow_status'], 'draft')

    def test_admin_role_can_delete_users_but_not_self(self):
        self.client.force_authenticate(self.admin)
        self.assertFalse(self.admin.is_staff)
        self.assertEqual(self.client.delete(f'/api/users/{self.admin.pk}/delete/').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/users/{self.other.pk}/delete/').status_code, 204)

    def test_journalist_cannot_manage_users_or_open_editor_dashboard(self):
        self.login(self.author)
        self.assertEqual(self.client.get('/api/user-list/').status_code, 403)
        self.assertEqual(self.client.get('/editor/dashboard/').status_code, 403)
        self.client.force_authenticate(self.author)
        self.assertEqual(self.client.delete(f'/api/users/{self.other.pk}/delete/').status_code, 403)

    def test_keep_signed_in_controls_browser_session_expiry(self):
        for remember in (False, True):
            self.client = APIClient(enforce_csrf_checks=True)
            self.client.get('/login-template/')
            response = self.client.post('/api/login/', {'username': self.author.username,
                'password': 'StrongPass123!', 'remember': remember}, format='json',
                HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.session.get_expire_at_browser_close(), not remember)

    def test_two_factor_login_requires_and_accepts_authenticator_code(self):
        secret = generate_secret()
        TwoFactorAuth.objects.create(user=self.author, secret=secret, is_enabled=True)
        response = self.login(self.author)
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.data['mfa_required'])
        response = self.client.post('/api/login/', {'username': self.author.username,
            'password': 'StrongPass123!', 'otp': totp(secret)}, format='json',
            HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)

    def test_refresh_renews_access_without_rotating_or_extending_refresh(self):
        login = self.login(self.author)
        refresh = login.data['token']['refresh']
        expires = RefreshToken(refresh)['exp']
        response = self.client.post('/api/token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(AccessToken(response.data['access'])['user_id']), str(self.author.pk))
        self.assertEqual(RefreshToken(refresh)['exp'], expires)

    def test_logout_prevents_refreshing_access(self):
        refresh = self.login(self.author).data['token']['refresh']
        self.client.post('/api/logout/', {'refresh': refresh}, format='json',
                         HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': refresh}, format='json').status_code, 401)

    def test_refresh_rejects_invalid_tokens_and_inactive_accounts(self):
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': 'invalid'}, format='json').status_code, 401)
        refresh = self.login(self.author).data['token']['refresh']
        self.author.is_active = False
        self.author.save(update_fields=['is_active'])
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': refresh}, format='json').status_code, 401)
