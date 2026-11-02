from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from articles.models import AIUsageEvent, AuditLog, OperationalAlert
from users.models import MembershipWebhookEvent, NotificationDelivery, PublicAPIKeyUsage, Workspace


class Command(BaseCommand):
    help = 'Delete expired operational, AI, API, and notification records while preserving editorial content.'

    def handle(self, *args, **options):
        now = timezone.now()
        ai_cutoff = now - timedelta(days=max(1, settings.AI_USAGE_RETENTION_DAYS))
        api_cutoff = now - timedelta(days=max(1, settings.API_USAGE_RETENTION_DAYS))
        default_cutoff = now - timedelta(days=max(1, settings.DATA_RETENTION_DAYS))
        audit_logs_deleted = AuditLog.objects.filter(workspace__isnull=True, created_at__lt=default_cutoff).delete()[0]
        ai_usage_deleted = AIUsageEvent.objects.filter(workspace__isnull=True, created_at__lt=ai_cutoff).delete()[0]
        for workspace in Workspace.objects.filter(is_active=True).only('id', 'retention_days'):
            cutoff = now - timedelta(days=max(30, workspace.retention_days))
            audit_logs_deleted += AuditLog.objects.filter(workspace=workspace, created_at__lt=cutoff).delete()[0]
            ai_usage_deleted += AIUsageEvent.objects.filter(workspace=workspace, created_at__lt=cutoff).delete()[0]
        deleted = {
            'audit_logs': audit_logs_deleted,
            'ai_usage_events': ai_usage_deleted,
            'api_usage_events': PublicAPIKeyUsage.objects.filter(created_at__lt=api_cutoff).delete()[0],
            'webhook_events': MembershipWebhookEvent.objects.filter(created_at__lt=default_cutoff).delete()[0],
            'notification_deliveries': NotificationDelivery.objects.filter(created_at__lt=api_cutoff).delete()[0],
            'resolved_alerts': OperationalAlert.objects.filter(status='resolved', resolved_at__lt=default_cutoff).delete()[0],
        }
        total = sum(deleted.values())
        self.stdout.write(self.style.SUCCESS(f'Retained active content and deleted {total} expired governance record(s): {deleted}'))
