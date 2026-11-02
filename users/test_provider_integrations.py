from unittest.mock import Mock, patch
import hashlib
import hmac
import time

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.billing_providers import cancel_remote_subscription, reconcile_pending_payments, verify_payment_webhook_signature
from users.models import CustomUser, MembershipInvoice, MembershipPlan, MembershipSubscription, PaymentTransaction


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

    @override_settings(STRIPE_WEBHOOK_SECRET='stripe-hook-secret')
    def test_stripe_native_signature_is_verified(self):
        body = b'{"id":"evt_1"}'
        timestamp = str(int(time.time()))
        digest = hmac.new(b'stripe-hook-secret', f'{timestamp}.{{"id":"evt_1"}}'.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(verify_payment_webhook_signature('stripe', body, {
            'Stripe-Signature': f't={timestamp},v1={digest}',
        }))

    @override_settings(STRIPE_SECRET_KEY='stripe-secret')
    @patch('users.billing_providers.requests.get')
    def test_reconciliation_marks_paid_transaction_and_invoice(self, get):
        transaction = PaymentTransaction.objects.create(
            user=self.user, plan=self.plan, provider='stripe', checkout_token='reconcile-token',
            provider_reference='cs_reconcile', amount=self.plan.price, currency=self.plan.currency,
        )
        MembershipInvoice.objects.create(
            invoice_number='INV-RECONCILE', user=self.user, plan=self.plan,
            transaction=transaction, amount=self.plan.price, currency=self.plan.currency,
        )
        get.return_value = Mock(ok=True, json=lambda: {'payment_status': 'paid', 'status': 'complete'})
        summary = reconcile_pending_payments()
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, 'succeeded')
        self.assertEqual(transaction.invoice.status, 'paid')
        self.assertEqual(summary['succeeded'], 1)
