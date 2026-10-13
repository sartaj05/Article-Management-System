from django.core.management.base import BaseCommand

from articles.backup import run_recovery_drill


class Command(BaseCommand):
    help = 'Verify that the latest database backup can be opened read-only.'

    def handle(self, *args, **options):
        drill = run_recovery_drill()
        if not drill:
            self.stderr.write(self.style.ERROR('No completed backup exists.'))
            return
        style = self.style.SUCCESS if drill.status == 'passed' else self.style.WARNING
        self.stdout.write(style(f'Recovery drill {drill.status}: {drill.details}'))
