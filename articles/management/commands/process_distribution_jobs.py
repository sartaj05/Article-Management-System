from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from users.delivery import dispatch_webhook_event
from articles.models import DistributionJob


class Command(BaseCommand):
    help = 'Process queued article distribution jobs.'

    def handle(self, *args, **options):
        jobs = DistributionJob.objects.filter(status='queued').filter(scheduled_for__isnull=True) | DistributionJob.objects.filter(status='queued', scheduled_for__lte=timezone.now())
        delivered = waiting = failed = 0
        for job in jobs.select_related('article', 'article__author')[:100]:
            with transaction.atomic():
                job = DistributionJob.objects.select_for_update().select_related('article', 'article__author').get(pk=job.pk)
                if job.status != 'queued':
                    continue
                job.status = 'processing'
                job.attempts += 1
                job.last_attempt_at = timezone.now()
                job.save(update_fields=['status', 'attempts', 'last_attempt_at'])
            try:
                if job.channel in {'webhook', 'rss'}:
                    deliveries = dispatch_webhook_event(owner=job.article.author, event_type='article.distribution_requested', payload={'article_id': job.article_id, 'channel': job.channel}) if job.channel == 'webhook' else []
                    if job.channel == 'webhook' and not deliveries:
                        job.status = 'failed'
                        job.last_error = 'No active webhook endpoint is configured.'
                        failed += 1
                    elif job.channel == 'webhook' and any(delivery.status != 'sent' for delivery in deliveries):
                        job.status = 'failed'
                        job.last_error = 'One or more webhook deliveries failed.'
                        failed += 1
                    else:
                        job.status = 'delivered'
                        job.delivered_at = timezone.now()
                        delivered += 1
                else:
                    job.status = 'awaiting_provider'
                    job.last_error = f'Configure the {job.channel} provider adapter before delivery.'
                    waiting += 1
                job.save(update_fields=['status', 'delivered_at', 'last_error'])
            except Exception as error:
                job.status = 'failed'
                job.last_error = str(error)[:500]
                job.save(update_fields=['status', 'last_error'])
                failed += 1
        self.stdout.write(self.style.SUCCESS(f'Delivered {delivered}; awaiting provider {waiting}; failed {failed}.'))
