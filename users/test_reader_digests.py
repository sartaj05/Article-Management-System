from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from articles.models import Notification
from .models import CustomUser, ReaderDigestDelivery, SavedSearch


class ReaderDigestTests(TestCase):
    def test_digest_command_records_delivery_and_is_idempotent(self):
        user = CustomUser.objects.create_user(username='digest-reader', email='digest@example.com', password='StrongPass123!', role='Journalist')
        SavedSearch.objects.create(user=user, name='Climate', query='climate', frequency='daily')
        notification = Notification.objects.create(recipient=user, notification_type='reader_alert', message='Climate story', digest_frequency='daily')
        call_command('send_reader_digests', frequency='daily')
        delivery = ReaderDigestDelivery.objects.get(user=user)
        self.assertEqual(delivery.status, 'sent')
        self.assertEqual(delivery.notification_count, 1)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.digest_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        call_command('send_reader_digests', frequency='daily')
        self.assertEqual(len(mail.outbox), 1)

    @patch('users.management.commands.send_reader_digests.send_mail', side_effect=[RuntimeError('SMTP unavailable'), 1])
    def test_failed_digest_can_be_retried(self, send_mail):
        user = CustomUser.objects.create_user(username='digest-retry', email='retry@example.com', password='StrongPass123!', role='Journalist')
        Notification.objects.create(recipient=user, notification_type='reader_alert', message='Retry story', digest_frequency='daily')
        call_command('send_reader_digests', frequency='daily')
        self.assertEqual(ReaderDigestDelivery.objects.get(user=user).status, 'failed')
        call_command('send_reader_digests', frequency='daily', retry_failed=True)
        self.assertEqual(send_mail.call_count, 2)
        self.assertEqual(ReaderDigestDelivery.objects.get(user=user).status, 'sent')
