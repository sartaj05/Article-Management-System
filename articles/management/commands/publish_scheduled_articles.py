from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from articles.models import Article
from articles.notifications import notify


class Command(BaseCommand):
    help = 'Publish approved articles whose scheduled publication time has arrived.'

    def handle(self, *args, **options):
        now = timezone.now()
        scheduled = Article.objects.filter(
            workflow_status='approved',
            scheduled_publish_at__isnull=False,
            scheduled_publish_at__lte=now,
        ).select_related('author')
        published_count = 0
        for article in scheduled:
            with transaction.atomic():
                article.workflow_status = 'published'
                article.review_status = 'approved'
                article.status = 'published'
                article.published_at = now
                article.publish_date = now.date()
                article.is_visible = True
                article.scheduled_publish_at = None
                article.save(update_fields=[
                    'workflow_status', 'review_status', 'status', 'published_at',
                    'publish_date', 'is_visible', 'scheduled_publish_at', 'updated_at',
                ])
                notify(
                    recipient=article.author,
                    article=article,
                    notification_type='published',
                    message=f'{article.title} was published automatically.',
                )
                published_count += 1
        self.stdout.write(self.style.SUCCESS(f'Published {published_count} scheduled article(s).'))
