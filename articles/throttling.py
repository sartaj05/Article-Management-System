import hashlib

from rest_framework.throttling import SimpleRateThrottle


class PublicFeedThrottle(SimpleRateThrottle):
    """Bound anonymous headless-feed traffic before it reaches the database."""

    scope = 'public_feed'

    def get_cache_key(self, request, view):
        api_key = request.headers.get('X-API-Key', '').strip()
        identity = f'key:{api_key}' if api_key else f'ip:{self.get_ident(request)}'
        digest = hashlib.sha256(identity.encode()).hexdigest()
        return f'throttle:{self.scope}:{digest}'
