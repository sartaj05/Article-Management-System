"""Guards for public interview/demo environments."""

from django.conf import settings
from django.http import JsonResponse

SAFE_PATHS = {'/demo/api/', '/logout/', '/api/logout/'}


def is_demo_user(user):
    return bool(getattr(user, 'is_authenticated', False) and str(user.username).startswith('demo_'))


class DemoSafetyMiddleware:
    """Make demo accounts read-only and prevent accidental provider calls."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEMO_MODE_ENABLED and is_demo_user(getattr(request, 'user', None)):
            if request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.path not in SAFE_PATHS:
                return JsonResponse({'detail': 'Demo accounts are read-only. Use Refresh workspace to reset the walkthrough.'}, status=403)
        return self.get_response(request)
