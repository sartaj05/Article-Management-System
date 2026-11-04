from .models import Notification
from users.delivery import deliver_email
from users.models import NotificationDelivery
from django.conf import settings
from django.db import transaction


def notify(*, recipient, notification_type, message, article=None):
    """Deliver an in-app and/or email notification according to user preferences."""
    preferences = getattr(recipient, 'notification_preferences', None)
    workflow_type = notification_type in {'submitted', 'approved', 'rejected', 'published', 'scheduled', 'assignment', 'sla_escalation'}
    enabled = preferences is None or (
        (preferences.workflow_enabled if workflow_type else preferences.comments_enabled)
    )
    notification = None
    if enabled and (preferences is None or preferences.in_app_enabled):
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            message=message,
            article=article,
        )
    if enabled and (preferences is None or preferences.email_enabled) and recipient.email:
        delivery = NotificationDelivery.objects.create(
            recipient=recipient,
            notification=notification,
            channel='email',
            payload={'subject': f'Article Management: {notification_type.title()}', 'message': message},
        )
        if settings.OUTBOX_ASYNC:
            transaction.on_commit(lambda delivery_id=delivery.id: _enqueue_email(delivery_id))
        else:
            deliver_email(delivery)
    return notification


def _enqueue_email(delivery_id):
    from users.tasks import deliver_email_task
    deliver_email_task.delay(delivery_id)
