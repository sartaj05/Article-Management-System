from django.core.management.base import BaseCommand
from django.utils import timezone

from articles.media_processing import generate_image_variants
from articles.models import MediaAsset


class Command(BaseCommand):
    help = 'Process pending image derivatives in the media library.'

    def handle(self, *args, **options):
        processed = failed = 0
        for asset in MediaAsset.objects.filter(processing_status__in=['pending', 'failed'], media_type='image', file__isnull=False):
            asset.processing_status = 'processing'
            asset.save(update_fields=['processing_status', 'updated_at'])
            try:
                generate_image_variants(asset)
                asset.processing_status = 'ready'
                asset.processed_at = timezone.now()
                asset.processing_error = ''
                asset.save(update_fields=['processing_status', 'processed_at', 'processing_error', 'updated_at'])
                processed += 1
            except (OSError, ValueError) as error:
                asset.processing_status = 'failed'
                asset.processing_error = str(error)[:255]
                asset.save(update_fields=['processing_status', 'processing_error', 'updated_at'])
                failed += 1
        self.stdout.write(self.style.SUCCESS(f'Processed {processed} media assets; {failed} failed.'))
