from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from articles.models import AIUsageEvent, AuditLog, OperationalAlert
from users.models import MembershipWebhookEvent, NotificationDelivery, PublicAPIKeyUsage


class Command(BaseCommand):
    help = 'Delete expired operational, AI, API, and notification records while preserving editorial content.'

    def handle(self, *args, **options):
        now = timezone.now()
        audit_cutoff = now - timedelta(days=max(1, settings.DATA_RETENTION_DAYS))
        ai_cutoff = now - timedelta(days=max(1, settings.AI_USAGE_RETENTION_DAYS))
        api_cutoff = now - timedelta(days=max(1, settings.API_USAGE_RETENTION_DAYS))
        deleted = {
            'audit_logs': AuditLog.objects.filter(created_at__lt=audit_cutoff).delete()[0],
            'ai_usage_events': AIUsageEvent.objects.filter(created_at__lt=ai_cutoff).delete()[0],
            'api_usage_events': PublicAPIKeyUsage.objects.filter(created_at__lt=api_cutoff).delete()[0],
            'webhook_events': MembershipWebhookEvent.objects.filter(created_at__lt=audit_cutoff).delete()[0],
            'notification_deliveries': NotificationDelivery.objects.filter(created_at__lt=api_cutoff).delete()[0],
            'resolved_alerts': OperationalAlert.objects.filter(status='resolved', resolved_at__lt=audit_cutoff).delete()[0],
        }
        total = sum(deleted.values())
        self.stdout.write(self.style.SUCCESS(f'Retained active content and deleted {total} expired governance record(s): {deleted}'))
