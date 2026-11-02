"""Fail-fast validation for production secrets and security settings."""

from django.conf import settings


PLACEHOLDER_MARKERS = ('change-this', 'replace-with', 'local-development', 'example.com')


def production_security_issues(config=settings):
    issues = []
    if config.DEBUG:
        issues.append('DJANGO_DEBUG must be false in production.')
    if len(config.SECRET_KEY) < 50 or any(marker in config.SECRET_KEY.lower() for marker in PLACEHOLDER_MARKERS):
        issues.append('DJANGO_SECRET_KEY must be a long, non-placeholder secret.')
    if not config.ALLOWED_HOSTS or '*' in config.ALLOWED_HOSTS:
        issues.append('DJANGO_ALLOWED_HOSTS must contain explicit hostnames and cannot be wildcarded.')
    if config.DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
        issues.append('Production must use PostgreSQL instead of SQLite.')
    if not config.SECURE_SSL_REDIRECT:
        issues.append('SECURE_SSL_REDIRECT must be true behind an HTTPS proxy.')
    if not config.SESSION_COOKIE_SECURE:
        issues.append('SESSION_COOKIE_SECURE must be true.')
    if not config.CSRF_COOKIE_SECURE:
        issues.append('CSRF_COOKIE_SECURE must be true.')
    if config.SECURE_HSTS_SECONDS < 31536000:
        issues.append('SECURE_HSTS_SECONDS must be at least one year.')
    if not config.CSRF_TRUSTED_ORIGINS:
        issues.append('CSRF_TRUSTED_ORIGINS must contain the public HTTPS origin.')
    if not getattr(config, 'METRICS_TOKEN', ''):
        issues.append('METRICS_TOKEN must be configured before exposing monitoring metrics.')
    if getattr(config, 'CORS_ALLOW_ALL_ORIGINS', False):
        issues.append('CORS_ALLOW_ALL_ORIGINS must remain false in production.')
    return issues
