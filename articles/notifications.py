from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


def notify(*, recipient, notification_type, message, article=None):
    """Deliver an in-app and/or email notification according to user preferences."""
    preferences = getattr(recipient, 'notification_preferences', None)
    workflow_type = notification_type in {'submitted', 'approved', 'rejected', 'published', 'scheduled'}
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
        send_mail(
            subject=f'Article Management: {notification_type.title()}',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=True,
        )
    return notification
