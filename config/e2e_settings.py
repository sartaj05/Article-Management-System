"""Settings only for the isolated local Playwright server."""

from copy import deepcopy
from .settings import *  # noqa: F403

DATABASES = deepcopy(DATABASES)  # noqa: F405
runtime_dir = BASE_DIR / 'test-runtime'  # noqa: F405
runtime_dir.mkdir(exist_ok=True)
DATABASES['default']['NAME'] = runtime_dir / 'db.sqlite3'

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
REST_FRAMEWORK = deepcopy(REST_FRAMEWORK)  # noqa: F405
# Browser suites share one loopback address and exercise hundreds of requests.
# Per-account failed-login protection remains active in UserLoginView.
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {'anon': '10000/hour', 'user': '10000/hour'}
