"""Encryption boundary for workspace integration credentials.

The key is expected to be injected as INTEGRATION_SECRET_KEY by the deployment
secret manager. Local development falls back to a deterministic key derived
from Django's SECRET_KEY so the application remains runnable without a cloud
provider, while production can rotate the integration key independently.
"""

import base64
import hashlib
import os

from django.conf import settings

from cryptography.fernet import Fernet, InvalidToken


class IntegrationSecretError(ValueError):
    """Raised when an integration secret cannot be encrypted or decrypted."""


def _fernet():
    configured_key = str(os.environ.get('INTEGRATION_SECRET_KEY', '')).strip()
    if configured_key:
        key = configured_key.encode('ascii')
    else:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise IntegrationSecretError('INTEGRATION_SECRET_KEY must be a valid Fernet key.') from exc


def encrypt_integration_secret(value):
    value = str(value or '').strip()
    return _fernet().encrypt(value.encode()).decode() if value else ''


def decrypt_integration_secret(value):
    value = str(value or '').strip()
    if not value:
        return ''
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise IntegrationSecretError('The integration secret could not be decrypted.') from exc
