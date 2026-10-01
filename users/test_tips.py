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
