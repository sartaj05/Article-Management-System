from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run the application background publishing cycle.'

    def handle(self, *args, **options):
        call_command('publish_scheduled_articles')
