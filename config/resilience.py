"""Small cache-backed circuit breaker for external provider calls."""

import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache


class CircuitOpenError(RuntimeError):
    pass


def _key(service):
    return f'provider-circuit:{service}'


def _state(service):
    return cache.get(_key(service), {'failures': 0, 'opened_until': 0})


def call_with_circuit(service, function):
    state = _state(service)
    if state.get('opened_until', 0) > time.time():
        raise CircuitOpenError(f'{service} provider circuit is open; retry later.')
    try:
        result = function()
    except Exception:
        failures = int(state.get('failures', 0)) + 1
        if failures >= settings.PROVIDER_CIRCUIT_FAILURE_THRESHOLD:
            state['opened_until'] = time.time() + settings.PROVIDER_CIRCUIT_COOLDOWN_SECONDS
        state['failures'] = failures
        cache.set(_key(service), state, timeout=settings.PROVIDER_CIRCUIT_COOLDOWN_SECONDS + 60)
        raise
    cache.delete(_key(service))
    return result


def protected(service):
    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            return call_with_circuit(service, lambda: function(*args, **kwargs))
        return wrapped
    return decorator
