"""Configuration-level health for external providers without exposing secrets."""

import importlib.util

from django.conf import settings


def provider_health():
    s3_configured = getattr(settings, 'MEDIA_STORAGE_BACKEND', 'filesystem') == 's3' and bool(
        getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
    )
    smtp_configured = bool(getattr(settings, 'EMAIL_HOST_USER', '') and getattr(settings, 'EMAIL_HOST_PASSWORD', ''))
    return {
        'payments': {
            'stripe': {'configured': bool(settings.STRIPE_SECRET_KEY and settings.PAYMENT_WEBHOOK_SECRET)},
            'razorpay': {'configured': bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET and settings.PAYMENT_WEBHOOK_SECRET)},
        },
        'email': {'configured': smtp_configured, 'backend': settings.EMAIL_BACKEND},
        'push': {
            'configured': bool(settings.VAPID_PRIVATE_KEY and settings.VAPID_CLAIMS_EMAIL and importlib.util.find_spec('pywebpush')),
            'vapid_configured': bool(settings.VAPID_PRIVATE_KEY and settings.VAPID_CLAIMS_EMAIL),
            'library_installed': bool(importlib.util.find_spec('pywebpush')),
        },
        'media': {
            'backend': getattr(settings, 'MEDIA_STORAGE_BACKEND', 'filesystem'),
            'configured': s3_configured or bool(getattr(settings, 'MEDIA_ROOT', '')),
        },
        'distribution': {
            'newsletter': {'configured': bool(settings.NEWSLETTER_PROVIDER_URL and settings.NEWSLETTER_PROVIDER_TOKEN)},
            'social': {'configured': bool(settings.SOCIAL_PROVIDER_URL and settings.SOCIAL_PROVIDER_TOKEN)},
            'webhooks': {'configured': True},
            'rss': {'configured': bool(settings.DISTRIBUTION_SITE_URL)},
        },
    }
