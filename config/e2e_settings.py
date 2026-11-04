"""Settings only for the isolated local Playwright server."""

from copy import deepcopy
import os
from .settings import *  # noqa: F403

DATABASES = deepcopy(DATABASES)  # noqa: F405
runtime_dir = BASE_DIR / 'test-runtime'  # noqa: F405
runtime_dir.mkdir(exist_ok=True)
database_name = os.getenv('E2E_DB_NAME', str(runtime_dir / 'db.sqlite3'))
DATABASES['default']['NAME'] = database_name
DATABASES['default']['OPTIONS'] = {
    'timeout': 60,
    'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
}
E2E_TEST_MODE = True

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
REST_FRAMEWORK = deepcopy(REST_FRAMEWORK)  # noqa: F405
# Browser suites share one loopback address and exercise hundreds of requests.
# Per-account failed-login protection remains active in UserLoginView.
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {'anon': '10000/hour', 'user': '10000/hour'}
# Browser suites intentionally exercise every role repeatedly from one
# loopback address. Keep the production five-attempt lockout in normal
# settings, but raise only the fixture-account threshold so long sequential
# suites do not become order-dependent after an expected invalid-login test.
LOGIN_FAILURE_LIMIT = 1000
