import logging

from django.db import transaction
from django.utils import timezone

from .audit import record_audit_event
from .models import Article
from .notifications import notify

logger = logging.getLogger(__name__)


def publish_scheduled_articles(now=None):
    """Publish due articles safely when multiple workers run the command."""

    now = now or timezone.now()
    due_ids = list(Article.objects.filter(
        workflow_status='approved',
        scheduled_publish_at__isnull=False,
        scheduled_publish_at__lte=now,
    ).values_list('id', flat=True))
    published_count = 0
    failed_ids = []

    for article_id in due_ids:
        try:
            with transaction.atomic():
                article = Article.objects.select_for_update().select_related('author').filter(
                    pk=article_id,
                    workflow_status='approved',
                    scheduled_publish_at__isnull=False,
                    scheduled_publish_at__lte=now,
                ).first()
                if article is None:
                    continue
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
                record_audit_event(actor=None, action='article_published_scheduled', article=article)
                notify(
                    recipient=article.author,
                    article=article,
                    notification_type='published',
                    message=f'{article.title} was published automatically.',
                )
                published_count += 1
        except Exception:
            failed_ids.append(article_id)
            logger.exception('Scheduled publishing failed for article %s', article_id)

    return {'published': published_count, 'failed_ids': failed_ids}
