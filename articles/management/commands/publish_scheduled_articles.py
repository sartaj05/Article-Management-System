from django.core.management.base import BaseCommand
from articles.jobs import publish_scheduled_articles


class Command(BaseCommand):
    help = 'Publish approved articles whose scheduled publication time has arrived.'

    def handle(self, *args, **options):
        result = publish_scheduled_articles()
        message = f"Published {result['published']} scheduled article(s)."
        if result['failed_ids']:
            message += f" Failed article IDs: {', '.join(map(str, result['failed_ids']))}."
        self.stdout.write(self.style.SUCCESS(message))
