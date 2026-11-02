import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from django.test import override_settings
from django.test import TestCase
from rest_framework.test import APIClient

from .models import AuthorTip, CustomUser


class AuthorTipFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.reader = CustomUser.objects.create_user(
            username='tip-reader', email='tip-reader@example.com', password='StrongPass123!', role='Journalist',
        )
        self.author = CustomUser.objects.create_user(
            username='tip-author', email='tip-author@example.com', password='StrongPass123!', role='Journalist',
        )
        self.client.force_authenticate(self.reader)

    def test_reader_can_create_tip_intent(self):
        response = self.client.post(f'/api/authors/{self.author.id}/tips/', {
            'amount': '250.00', 'currency': 'INR', 'message': 'Thank you for this story.',
        }, format='json')
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data['payment_required'])
        self.assertEqual(AuthorTip.objects.get().status, 'pending')

    def test_tip_amount_must_be_positive(self):
        response = self.client.post(f'/api/authors/{self.author.id}/tips/', {'amount': '0'}, format='json')
        self.assertEqual(response.status_code, 400)

    @override_settings(STRIPE_SECRET_KEY='sk_test_example')
    @patch('users.billing_providers.requests.post')
    def test_stripe_tip_checkout_returns_session(self, post):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {'id': 'cs_tip_123', 'url': 'https://checkout.stripe.test/tip'})
        response = self.client.post(f'/api/authors/{self.author.id}/tips/', {
            'amount': '25.00', 'currency': 'INR', 'provider': 'stripe',
        }, format='json')
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data['provider_configured'])
        tip = AuthorTip.objects.get()
        self.assertEqual(tip.provider_reference, 'cs_tip_123')
        self.assertEqual(tip.checkout_url, 'https://checkout.stripe.test/tip')
        self.assertEqual(post.call_args.kwargs['data']['mode'], 'payment')

    @override_settings(PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_tip_webhook_marks_tip_succeeded_and_is_idempotent(self):
        self.client.post(f'/api/authors/{self.author.id}/tips/', {
            'amount': '25.00', 'currency': 'INR', 'provider': 'manual',
        }, format='json')
        tip = AuthorTip.objects.get()
        payload = {
            'id': 'evt_tip_1', 'type': 'payment.captured', 'provider': 'razorpay',
            'data': {'tip_id': tip.id, 'provider_reference': 'pay_tip_1'},
        }
        body = json.dumps(payload).encode()
        signature = 'sha256=' + hmac.new(b'test-webhook-secret', body, hashlib.sha256).hexdigest()
        response = self.client.post('/api/membership/webhook/', body, content_type='application/json', HTTP_X_PAYMENT_SIGNATURE=signature)
        self.assertEqual(response.status_code, 200)
        tip.refresh_from_db()
        self.assertEqual(tip.status, 'succeeded')
        self.assertEqual(tip.provider_reference, 'pay_tip_1')
        duplicate = self.client.post('/api/membership/webhook/', body, content_type='application/json', HTTP_X_PAYMENT_SIGNATURE=signature)
        self.assertTrue(duplicate.data['duplicate'])
