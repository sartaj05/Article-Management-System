from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone

from articles.models import Notification
from users.models import NotificationPreference


class Command(BaseCommand):
    help = 'Send daily or weekly email digests for reader alerts.'

    def add_arguments(self, parser):
        parser.add_argument('--frequency', choices=['daily', 'weekly'], default='daily')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        frequency = options['frequency']
        now = timezone.now()
        since = now - timedelta(days=1 if frequency == 'daily' else 7)
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
            if not options['dry_run']:
                send_mail(
                    subject=f'Your Article Studio {frequency} reader digest',
                    message='\n\n'.join(lines),
                    from_email=None,
                    recipient_list=[recipient.email],
                    fail_silently=True,
                )
                Notification.objects.filter(pk__in=[item.pk for item in items]).update(digest_sent_at=now)
            sent += 1
        self.stdout.write(self.style.SUCCESS(f'Prepared {sent} {frequency} reader digest(s).'))
