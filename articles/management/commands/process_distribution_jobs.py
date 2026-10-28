from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from articles.distribution_providers import ProviderDeliveryError, ProviderNotConfigured, deliver_job
from articles.models import DistributionJob


class Command(BaseCommand):
    help = 'Process queued article distribution jobs.'

    def handle(self, *args, **options):
        jobs = DistributionJob.objects.filter(status='queued').filter(scheduled_for__isnull=True) | DistributionJob.objects.filter(status='queued', scheduled_for__lte=timezone.now())
        delivered = waiting = failed = 0
        for queued_job in jobs.select_related('article', 'article__author')[:100]:
            with transaction.atomic():
                job = DistributionJob.objects.select_for_update().select_related('article', 'article__author').get(pk=queued_job.pk)
                if job.status != 'queued':
                    continue
                job.status = 'processing'
                job.attempts += 1
                job.last_attempt_at = timezone.now()
                job.save(update_fields=['status', 'attempts', 'last_attempt_at'])
            try:
                delivery = deliver_job(job)
                job.status = 'delivered'
                job.provider_reference = delivery.get('reference', '')[:160]
                job.provider_response = delivery.get('response', {})
                job.delivered_at = timezone.now()
                delivered += 1
            except ProviderNotConfigured as error:
                job.status = 'awaiting_provider'
                job.last_error = str(error)[:500] or f'Configure the {job.channel} provider adapter before delivery.'
                waiting += 1
            except ProviderDeliveryError as error:
                job.status = 'failed'
                job.last_error = str(error)[:500]
                failed += 1
            except Exception as error:
                job.status = 'failed'
                job.last_error = str(error)[:500]
                failed += 1
            job.save(update_fields=['status', 'delivered_at', 'last_error', 'provider_reference', 'provider_response'])
        self.stdout.write(self.style.SUCCESS(f'Delivered {delivered}; awaiting provider {waiting}; failed {failed}.'))
