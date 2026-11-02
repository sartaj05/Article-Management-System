from django.core.management.base import BaseCommand, CommandError

from articles.queue_health import inspect_workers


class Command(BaseCommand):
    help = 'Fail when no Celery worker responds to a bounded health check.'

    def handle(self, *args, **options):
        snapshot = inspect_workers()
        if snapshot['status'] != 'healthy':
            raise CommandError(snapshot.get('error') or 'No healthy Celery workers found.')
        self.stdout.write(self.style.SUCCESS(f"{len(snapshot['workers'])} Celery worker(s) healthy"))
