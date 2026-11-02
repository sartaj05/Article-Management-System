from types import SimpleNamespace

from django.test import SimpleTestCase

from config.security import production_security_issues


class SecurityReleaseTests(SimpleTestCase):
    def test_secure_production_configuration_has_no_issues(self):
        config = SimpleNamespace(
            DEBUG=False,
            SECRET_KEY='a' * 64,
            ALLOWED_HOSTS=['news.example.org'],
            DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql'}},
            SECURE_SSL_REDIRECT=True,
            SESSION_COOKIE_SECURE=True,
            CSRF_COOKIE_SECURE=True,
            SECURE_HSTS_SECONDS=31536000,
            CSRF_TRUSTED_ORIGINS=['https://news.example.org'],
            METRICS_TOKEN='monitoring-token',
            CORS_ALLOW_ALL_ORIGINS=False,
        )
        self.assertEqual(production_security_issues(config), [])

    def test_insecure_production_configuration_is_reported(self):
        config = SimpleNamespace(
            DEBUG=True,
            SECRET_KEY='replace-with-a-short-secret',
            ALLOWED_HOSTS=['*'],
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3'}},
            SECURE_SSL_REDIRECT=False,
            SESSION_COOKIE_SECURE=False,
            CSRF_COOKIE_SECURE=False,
            SECURE_HSTS_SECONDS=0,
            CSRF_TRUSTED_ORIGINS=[],
            METRICS_TOKEN='',
            CORS_ALLOW_ALL_ORIGINS=True,
        )
        self.assertGreaterEqual(len(production_security_issues(config)), 8)
