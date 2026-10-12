from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from articles.models import MediaAsset


class Command(BaseCommand):
    help = 'Archive unreferenced media assets older than the selected age.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--apply', action='store_true', help='Archive the matching assets.')

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=max(1, options['days']))
        orphaned = MediaAsset.objects.filter(
            is_archived=False,
            article_links__isnull=True,
            updated_at__lt=cutoff,
        ).distinct()
        count = orphaned.count()
        if options['apply']:
            orphaned.update(is_archived=True, updated_at=timezone.now())
            self.stdout.write(self.style.SUCCESS(f'Archived {count} orphaned media asset(s).'))
        else:
            self.stdout.write(f'{count} orphaned media asset(s) would be archived. Use --apply to change them.')
