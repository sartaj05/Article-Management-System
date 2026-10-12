from django.core.management.base import BaseCommand

from articles.media_processing import generate_image_variants
from articles.models import MediaAsset


class Command(BaseCommand):
    help = 'Generate responsive WebP variants for image assets.'

    def handle(self, *args, **options):
        processed = failed = 0
        for asset in MediaAsset.objects.filter(media_type='image', is_archived=False, file__isnull=False):
            try:
                generate_image_variants(asset)
                processed += 1
            except (OSError, ValueError) as error:
                failed += 1
                self.stderr.write(f'Asset {asset.pk}: {error}')
        self.stdout.write(self.style.SUCCESS(f'Processed {processed} image assets; {failed} failed.'))
