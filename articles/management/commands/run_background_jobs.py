from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run the application background publishing cycle.'

    def handle(self, *args, **options):
        for command in (
            'publish_scheduled_articles',
            'process_distribution_jobs',
            'send_assignment_reminders',
            'send_assignment_escalations',
        ):
            call_command(command)
