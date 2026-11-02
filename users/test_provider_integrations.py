from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.billing_providers import cancel_remote_subscription
from users.models import CustomUser, MembershipPlan, MembershipSubscription


class ProviderIntegrationTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='provider-admin', email='provider-admin@example.com', password='StrongPass123!', role='Admin')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.plan = MembershipPlan.objects.create(name='Provider plan', slug='provider-plan', price=10, currency='USD', interval='month', is_active=True)

    def test_provider_health_hides_secrets_and_reports_configuration(self):
        response = self.client.get('/provider-health/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('payments', response.data)
        self.assertNotIn('STRIPE_SECRET_KEY', str(response.data))

    @override_settings(PAYMENT_REMOTE_CANCELLATION_ENABLED=True, STRIPE_SECRET_KEY='stripe-secret')
    @patch('users.billing_providers.requests.delete')
    def test_stripe_subscription_is_cancelled_remotely(self, delete):
        delete.return_value = Mock(ok=True, content=b'{}', json=lambda: {})
        subscription = MembershipSubscription.objects.create(user=self.user, plan=self.plan, provider='stripe', provider_reference='sub_123', status='active')
        result = cancel_remote_subscription(subscription)
        self.assertTrue(result['canceled'])
        delete.assert_called_once()
