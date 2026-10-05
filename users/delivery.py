import json
import hashlib
import hmac
import logging
from uuid import uuid4

from django.conf import settings
from django.utils import timezone
import requests

from .models import WebhookDelivery, WebhookEndpoint

logger = logging.getLogger(__name__)


def dispatch_webhook_event(*, owner, event_type, payload):
    """Deliver an event to the owner's subscribed webhook endpoints."""
    body = json.dumps(payload, default=str, sort_keys=True).encode('utf-8')
    deliveries = []
    endpoints = WebhookEndpoint.objects.filter(owner=owner, is_active=True)
    for endpoint in endpoints:
        if endpoint.events and event_type not in endpoint.events:
            continue
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type=event_type, payload=payload,
        )
        signature = hmac.new(endpoint.secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
        delivery.attempts = 1
        try:
            response = requests.post(
                endpoint.url,
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'X-Webhook-Event': event_type,
                    'X-Webhook-Id': str(delivery.event_id),
                    'X-Webhook-Signature': f'sha256={signature}',
                },
                timeout=5,
            )
            delivery.response_code = response.status_code
            delivery.status = 'sent' if 200 <= response.status_code < 300 else 'failed'
            if delivery.status == 'sent':
                delivery.delivered_at = timezone.now()
            else:
                delivery.last_error = f'Endpoint returned HTTP {response.status_code}'
        except Exception as exc:
            delivery.status = 'failed'
            delivery.last_error = str(exc)[:500]
            logger.warning('Webhook delivery failed: %s', exc)
        delivery.save(update_fields=['attempts', 'response_code', 'status', 'last_error', 'delivered_at'])
        deliveries.append(delivery)
    return deliveries


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
