from django.core.management.base import BaseCommand
from django.utils import timezone

from users.delivery import dispatch_webhook_event
from articles.models import DistributionJob


class Command(BaseCommand):
    help = 'Process queued article distribution jobs.'

    def handle(self, *args, **options):
        jobs = DistributionJob.objects.filter(status='queued').filter(scheduled_for__isnull=True) | DistributionJob.objects.filter(status='queued', scheduled_for__lte=timezone.now())
        delivered = waiting = failed = 0
        for job in jobs.select_related('article', 'article__author')[:100]:
            job.status = 'processing'
            job.attempts += 1
            job.save(update_fields=['status', 'attempts'])
            try:
                if job.channel == 'webhook':
                    dispatch_webhook_event(owner=job.article.author, event_type='article.distribution_requested', payload={'article_id': job.article_id, 'channel': job.channel})
                    job.status = 'delivered'
                    job.delivered_at = timezone.now()
                    delivered += 1
                else:
                    job.status = 'awaiting_provider'
                    job.last_error = 'Configure the channel provider adapter before delivery.'
                    waiting += 1
                job.save(update_fields=['status', 'delivered_at', 'last_error'])
            except Exception as error:
                job.status = 'failed'
                job.last_error = str(error)[:500]
                job.save(update_fields=['status', 'last_error'])
                failed += 1
        self.stdout.write(self.style.SUCCESS(f'Delivered {delivered}; awaiting provider {waiting}; failed {failed}.'))
