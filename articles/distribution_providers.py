from django.conf import settings
from django.urls import reverse
import json
import requests

from users.delivery import dispatch_webhook_event


class ProviderNotConfigured(Exception):
    pass


class ProviderDeliveryError(Exception):
    pass


def _article_payload(job):
    article = job.article
    base_url = getattr(settings, 'DISTRIBUTION_SITE_URL', '').rstrip('/')
    return {
        'article_id': article.id,
        'title': article.title,
        'summary': article.summary or article.content[:300],
        'content': article.content,
        'url': f'{base_url}{reverse("public-article", kwargs={"slug": article.slug})}',
        'channel': job.channel,
    }


def _http_delivery(url, token, payload):
    if not url or not token:
        raise ProviderNotConfigured
    response = requests.post(url, json=payload, headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}, timeout=settings.DISTRIBUTION_HTTP_TIMEOUT)
    if response.status_code >= 400:
        raise ProviderDeliveryError(f'Provider returned HTTP {response.status_code}.')
    if isinstance(response.content, (bytes, bytearray)) and response.content:
        raw_body = json.loads(response.content.decode('utf-8'))
    elif isinstance(response.content, str) and response.content:
        raw_body = json.loads(response.content)
    else:
        raw_body = {}
    body = raw_body if isinstance(raw_body, dict) else {}
    return {'reference': str(body.get('id') or body.get('reference') or response.headers.get('X-Request-Id') or ''), 'response': body}


def deliver_job(job):
    payload = _article_payload(job)
    if job.channel == 'rss':
        return {'reference': f'rss:{job.article.slug}', 'response': {'feed_url': f'{getattr(settings, "DISTRIBUTION_SITE_URL", "").rstrip("/")}/rss.xml'}}
    if job.channel == 'webhook':
        deliveries = dispatch_webhook_event(owner=job.article.author, event_type='article.distribution_requested', payload=payload)
        if not deliveries:
            raise ProviderNotConfigured('No active webhook endpoint is configured.')
        if any(delivery.status != 'sent' for delivery in deliveries):
            raise ProviderDeliveryError('One or more webhook deliveries failed.')
        return {'reference': ','.join(str(delivery.id) for delivery in deliveries), 'response': {'deliveries': len(deliveries)}}
    if job.channel == 'newsletter':
        return _http_delivery(getattr(settings, 'NEWSLETTER_PROVIDER_URL', ''), getattr(settings, 'NEWSLETTER_PROVIDER_TOKEN', ''), payload)
    if job.channel == 'social':
        return _http_delivery(getattr(settings, 'SOCIAL_PROVIDER_URL', ''), getattr(settings, 'SOCIAL_PROVIDER_TOKEN', ''), payload)
    raise ProviderDeliveryError(f'Unsupported distribution channel: {job.channel}')
