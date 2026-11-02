from django.core.management.base import BaseCommand

from articles.backup import create_media_backup


class Command(BaseCommand):
    help = 'Create a media archive or object-storage media manifest.'

    def handle(self, *args, **options):
        record = create_media_backup()
        if record.status == 'completed':
            self.stdout.write(self.style.SUCCESS(f'Media backup {record.id} created: {record.path}'))
        else:
            self.stderr.write(self.style.ERROR(f'Media backup failed: {record.error}'))
