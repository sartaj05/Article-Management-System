from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from articles.models import MediaAsset
from django.core.files.storage import default_storage


class Command(BaseCommand):
    help = 'Archive unreferenced media assets older than the selected age.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--apply', action='store_true', help='Archive the matching assets.')
        parser.add_argument('--purge', action='store_true', help='Delete archived files older than --days.')

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
        if options['purge']:
            archived = MediaAsset.objects.filter(is_archived=True, updated_at__lt=cutoff).only('id', 'file', 'metadata')
            purged = 0
            for asset in archived.iterator():
                if asset.file:
                    default_storage.delete(asset.file.name)
                for path in (asset.metadata or {}).get('variants', {}).values():
                    default_storage.delete(path)
                purged += 1
            self.stdout.write(self.style.SUCCESS(f'Purged files for {purged} archived media asset(s).'))
