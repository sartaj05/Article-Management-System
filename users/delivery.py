import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_web_push(subscription, payload):
    """Deliver a push message when pywebpush and VAPID settings are configured.

    Returning a status instead of raising keeps local development usable without
    a browser push provider. Production can install pywebpush and configure VAPID.
    """
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_CLAIMS_EMAIL:
        return {'sent': False, 'reason': 'web_push_not_configured'}
    try:
        from pywebpush import webpush
        webpush(
            subscription_info={'endpoint': subscription.endpoint, 'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth}},
            data=json.dumps(payload), vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={'sub': f'mailto:{settings.VAPID_CLAIMS_EMAIL}'},
        )
        return {'sent': True}
    except ImportError:
        return {'sent': False, 'reason': 'pywebpush_not_installed'}
    except Exception as exc:
        logger.warning('Web push delivery failed: %s', exc)
        return {'sent': False, 'reason': 'delivery_failed'}
