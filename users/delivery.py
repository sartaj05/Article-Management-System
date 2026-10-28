import json
import hashlib
import hmac
import logging
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone
import requests

from .models import AlertRule, NotificationPreference, PushSubscription, SavedSearch, WebhookDelivery, WebhookEndpoint

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


def retry_webhook_delivery(delivery):
    """Retry one failed delivery while preserving its event id and audit trail."""
    body = json.dumps(delivery.payload, default=str, sort_keys=True).encode('utf-8')
    signature = hmac.new(delivery.endpoint.secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    delivery.attempts += 1
    try:
        response = requests.post(
            delivery.endpoint.url, data=body,
            headers={'Content-Type': 'application/json', 'X-Webhook-Event': delivery.event_type, 'X-Webhook-Id': str(delivery.event_id), 'X-Webhook-Signature': f'sha256={signature}'},
            timeout=5,
        )
        delivery.response_code = response.status_code
        delivery.status = 'sent' if 200 <= response.status_code < 300 else 'failed'
        delivery.last_error = '' if delivery.status == 'sent' else f'Endpoint returned HTTP {response.status_code}'
        delivery.delivered_at = timezone.now() if delivery.status == 'sent' else None
    except Exception as exc:
        delivery.status = 'failed'
        delivery.last_error = str(exc)[:500]
    delivery.save(update_fields=['attempts', 'response_code', 'status', 'last_error', 'delivered_at'])
    return delivery


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


def dispatch_article_alert(*, article, title=None, body=None):
    """Create reader alerts and send best-effort instant push notifications."""
    from articles.models import Notification

    rule_matches = AlertRule.objects.filter(is_active=True).filter(
        models.Q(rule_type='all') |
        models.Q(rule_type='category', value__iexact=article.category or '') |
        models.Q(rule_type='author', value=str(article.author_id)) |
        models.Q(rule_type='author', value__iexact=article.author.username),
    ).values_list('user_id', flat=True).distinct()
    searchable_text = ' '.join(filter(None, [article.title, article.summary, article.category, article.tags])).casefold()
    search_matches = [
        saved_search for saved_search in SavedSearch.objects.filter(is_active=True)
        if saved_search.query.casefold() in searchable_text
    ]
    matching = set(rule_matches).union(saved_search.user_id for saved_search in search_matches)
    instant_users = set(rule_matches).union(
        saved_search.user_id for saved_search in search_matches if saved_search.frequency == 'instant'
    )
    payload = {'title': title or article.title, 'body': body or (article.summary or article.content[:160]), 'url': f'/articles/read/{article.slug}/', 'article_id': article.id}
    message = body or (article.summary or article.content[:160])
    search_frequency = {saved_search.user_id: saved_search.frequency for saved_search in search_matches}
    in_app_preferences = dict(NotificationPreference.objects.filter(user_id__in=matching).values_list('user_id', 'in_app_enabled'))
    for user_id in matching:
        if not in_app_preferences.get(user_id, True):
            continue
        notification, created = Notification.objects.get_or_create(
            recipient_id=user_id,
            article=article,
            notification_type='reader_alert',
            defaults={
                'message': message,
                'action_url': payload['url'],
                'digest_frequency': search_frequency.get(user_id, 'instant'),
            },
        )
        if not created and not notification.action_url:
            notification.action_url = payload['url']
            notification.save(update_fields=['action_url'])
    results = []
    for subscription in PushSubscription.objects.filter(user_id__in=instant_users, is_active=True):
        result = send_web_push(subscription, payload)
        results.append({'subscription_id': subscription.id, **result})
    return results
