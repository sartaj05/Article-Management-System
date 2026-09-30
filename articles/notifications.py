from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


def notify(*, recipient, notification_type, message, article=None):
    """Create an in-app notification and best-effort email notification."""
    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        message=message,
        article=article,
    )
    if recipient.email:
        send_mail(
            subject=f'Article Management: {notification_type.title()}',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=True,
        )
    return notification
