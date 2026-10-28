from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone

from articles.models import Notification
from users.models import NotificationPreference, ReaderDigestDelivery


class Command(BaseCommand):
    help = 'Send daily or weekly email digests for reader alerts.'

    def add_arguments(self, parser):
        parser.add_argument('--frequency', choices=['daily', 'weekly'], default='daily')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--retry-failed', action='store_true')

    def handle(self, *args, **options):
        frequency = options['frequency']
        now = timezone.now()
        since = now - timedelta(days=1 if frequency == 'daily' else 7)
        period_key = now.date() if frequency == 'daily' else (now - timedelta(days=now.weekday())).date()
        notifications = Notification.objects.filter(
            notification_type='reader_alert',
            digest_frequency=frequency,
            digest_sent_at__isnull=True,
            created_at__gte=since,
            created_at__lte=now,
        ).select_related('recipient', 'article')
        grouped = defaultdict(list)
        for notification in notifications:
            preference = NotificationPreference.objects.filter(user=notification.recipient).first()
            if preference is not None and not preference.email_enabled:
                continue
            if notification.recipient.email:
                grouped[notification.recipient].append(notification)

        sent = 0
        for recipient, items in grouped.items():
            lines = [f"{item.article.title if item.article else 'Article Studio alert'}\n{item.message}\n{item.action_url}" for item in items]
            delivery, created = ReaderDigestDelivery.objects.get_or_create(
                user=recipient,
                frequency=frequency,
                period_key=period_key,
                defaults={'notification_count': len(items)},
            )
            if delivery.status == 'sent' or (delivery.status == 'failed' and not options['retry_failed']):
                continue
            if not options['dry_run']:
                delivery.status = 'sending'
                delivery.attempts += 1
                delivery.notification_count = len(items)
                delivery.last_error = ''
                delivery.save(update_fields=['status', 'attempts', 'notification_count', 'last_error'])
                try:
                    send_mail(
                        subject=f'Your Article Studio {frequency} reader digest',
                        message='\n\n'.join(lines),
                        from_email=None,
                        recipient_list=[recipient.email],
                        fail_silently=False,
                    )
                    Notification.objects.filter(pk__in=[item.pk for item in items]).update(digest_sent_at=now)
                    delivery.status = 'sent'
                    delivery.sent_at = now
                    delivery.save(update_fields=['status', 'sent_at'])
                except Exception as error:
                    delivery.status = 'failed'
                    delivery.last_error = str(error)[:500]
                    delivery.save(update_fields=['status', 'last_error'])
            sent += 1
        self.stdout.write(self.style.SUCCESS(f'Prepared {sent} {frequency} reader digest(s).'))
