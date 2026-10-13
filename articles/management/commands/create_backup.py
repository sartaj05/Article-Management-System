from django.core.management.base import BaseCommand

from articles.backup import create_database_backup


class Command(BaseCommand):
    help = 'Create and checksum a database backup.'

    def handle(self, *args, **options):
        record = create_database_backup()
        if record.status == 'completed':
            self.stdout.write(self.style.SUCCESS(f'Backup {record.id} created: {record.path}'))
        else:
            self.stderr.write(self.style.ERROR(f'Backup failed: {record.error}'))
