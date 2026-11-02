from django.core.management.base import BaseCommand

from articles.backup import prune_old_backups


class Command(BaseCommand):
    help = 'Delete backup files and records older than BACKUP_RETENTION_DAYS.'

    def handle(self, *args, **options):
        deleted = prune_old_backups()
        self.stdout.write(self.style.SUCCESS(f'Pruned {deleted} backup record(s).'))
