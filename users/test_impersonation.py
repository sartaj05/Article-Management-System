from django.test import TestCase
from rest_framework.test import APIClient

from articles.models import AuditLog
from .models import CustomUser, ImpersonationSession


class AdminImpersonationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(username='impersonation-admin', email='imp-admin@example.com', password='StrongPass123!', role='Admin')
        self.target = CustomUser.objects.create_user(username='impersonation-target', email='target@example.com', password='StrongPass123!', role='Editor')
        self.assertTrue(self.client.login(username=self.admin.username, password='StrongPass123!'))

    def test_impersonation_is_short_lived_and_audited(self):
        response = self.client.post('/api/security/impersonation/', {'user_id': self.target.id, 'reason': 'Support ticket investigation'}, format='json')
        self.assertEqual(response.status_code, 201)
        session = ImpersonationSession.objects.get(pk=response.data['session_id'])
        self.assertEqual(session.admin_id, self.admin.id)
        self.assertEqual(session.target_id, self.target.id)

        active = self.client.get('/api/security/impersonation/')
        self.assertEqual(active.status_code, 200)
        self.assertTrue(active.data['active'])
        self.assertEqual(active.data['target'], self.target.username)

        ended = self.client.delete('/api/security/impersonation/')
        self.assertEqual(ended.status_code, 200)
        session.refresh_from_db()
        self.assertIsNotNone(session.ended_at)
        self.assertEqual(AuditLog.objects.filter(action__in=['impersonation_started', 'impersonation_ended']).count(), 2)

        inactive = self.client.get('/api/security/impersonation/')
        self.assertFalse(inactive.data['active'])

    def test_non_admin_cannot_start_impersonation(self):
        self.client.logout()
        self.client.login(username=self.target.username, password='StrongPass123!')
        response = self.client.post('/api/security/impersonation/', {'user_id': self.admin.id, 'reason': 'not allowed'}, format='json')
        self.assertEqual(response.status_code, 403)
