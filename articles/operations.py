"""Persisted operational alert evaluation for newsroom reliability signals."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from config.observability import request_error_rate
from users.models import MembershipWebhookEvent, PaymentTransaction, ReaderDigestDelivery, WebhookDelivery
from users.provider_health import provider_health

from .models import ArticleAssignment, BackupRecord, DistributionJob, OperationalAlert


def collect_operational_alerts():
    now = timezone.now()
    summary = {
        'distribution_failed': DistributionJob.objects.filter(status='failed').count(),
        'distribution_queued': DistributionJob.objects.filter(status__in={'queued', 'processing', 'awaiting_provider'}).count(),
        'webhook_failed': WebhookDelivery.objects.filter(status='failed').count(),
        'digest_failed': ReaderDigestDelivery.objects.filter(status='failed').count(),
        'overdue_assignments': ArticleAssignment.objects.filter(due_at__lt=now).exclude(status='done').count(),
        'payment_events_24h': MembershipWebhookEvent.objects.filter(created_at__gte=now - timedelta(hours=24)).count(),
    }
    alerts = []
    rules = [
        ('distribution.failed', 'Distribution', 'high', summary['distribution_failed'], f"{summary['distribution_failed']} distribution job(s) failed."),
        ('webhooks.failed', 'Webhooks', 'high', summary['webhook_failed'], f"{summary['webhook_failed']} webhook delivery(ies) failed."),
        ('digests.failed', 'Reader digests', 'medium', summary['digest_failed'], f"{summary['digest_failed']} reader digest delivery(ies) failed."),
        ('editorial.sla', 'Editorial SLA', 'medium', summary['overdue_assignments'], f"{summary['overdue_assignments']} assignment(s) are overdue."),
    ]
    for fingerprint, area, severity, count, message in rules:
        if count:
            alerts.append({'fingerprint': fingerprint, 'area': area, 'severity': severity, 'message': message, 'details': {'count': count}})
    queue_age = DistributionJob.objects.filter(
        status__in={'queued', 'processing', 'awaiting_provider'},
        created_at__lt=now - timedelta(minutes=settings.OPERATIONS_QUEUE_DELAY_MINUTES),
    ).count()
    if queue_age:
        alerts.append({'fingerprint': 'queue.delay', 'area': 'Queue', 'severity': 'low', 'message': f'{queue_age} distribution job(s) exceeded the queue delay SLO.', 'details': {'count': queue_age, 'threshold_minutes': settings.OPERATIONS_QUEUE_DELAY_MINUTES}})
    recent_backup_failure = BackupRecord.objects.filter(status='failed', created_at__gte=now - timedelta(hours=24)).first()
    if recent_backup_failure:
        alerts.append({'fingerprint': 'backups.failed', 'area': 'Backups', 'severity': 'critical', 'message': 'A backup failed in the last 24 hours.', 'details': {'backup_id': recent_backup_failure.id, 'error': recent_backup_failure.error}})
    error_rate = request_error_rate()
    if error_rate['total'] >= 20 and error_rate['rate'] >= settings.OPERATIONS_ERROR_RATE_THRESHOLD:
        alerts.append({'fingerprint': 'http.error-rate', 'area': 'HTTP', 'severity': 'critical', 'message': f"HTTP error rate is {error_rate['rate']:.1%} over the recent window.", 'details': error_rate})
    health = provider_health()
    for provider, configured in (
        ('stripe', health['payments']['stripe']['configured']),
        ('razorpay', health['payments']['razorpay']['configured']),
    ):
        pending = PaymentTransaction.objects.filter(provider=provider, status='pending').count()
        if pending and not configured:
            alerts.append({'fingerprint': f'provider.{provider}', 'area': 'Payments', 'severity': 'high', 'message': f'{provider.title()} has pending payments but is not configured.', 'details': {'pending': pending}})
    return summary, alerts


def refresh_operational_alerts():
    summary, current = collect_operational_alerts()
    now = timezone.now()
    fingerprints = set()
    for item in current:
        fingerprints.add(item['fingerprint'])
        alert, created = OperationalAlert.objects.get_or_create(
            fingerprint=item['fingerprint'],
            defaults={**item, 'occurrences': 1, 'first_seen_at': now, 'last_seen_at': now},
        )
        if not created:
            alert.area = item['area']
            alert.severity = item['severity']
            alert.message = item['message']
            alert.details = item.get('details', {})
            alert.occurrences += 1
            alert.last_seen_at = now
            if alert.status == 'resolved':
                alert.status = 'open'
                alert.resolved_at = None
            alert.save(update_fields=['area', 'severity', 'message', 'details', 'occurrences', 'last_seen_at', 'status', 'resolved_at'])
    OperationalAlert.objects.filter(status__in={'open', 'acknowledged'}).exclude(fingerprint__in=fingerprints).update(status='resolved', resolved_at=now)
    return {'summary': summary, 'alerts': list(OperationalAlert.objects.filter(status__in={'open', 'acknowledged'}))}
