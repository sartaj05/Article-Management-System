import uuid

from django.conf import settings

from .observability import request_id_context


class RequestIDMiddleware:
    """Attach a stable correlation ID to every response and request log context."""

    header_name = 'X-Request-ID'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get(self.header_name) or uuid.uuid4().hex
        token = request_id_context.set(request.request_id)
        try:
            response = self.get_response(request)
            response[self.header_name] = request.request_id
            return response
        finally:
            request_id_context.reset(token)


class SecurityHeadersMiddleware:
    """Add deployment-controlled browser security headers to every response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(settings, 'SECURITY_CSP', ''):
            response.setdefault('Content-Security-Policy', settings.SECURITY_CSP)
        if getattr(settings, 'SECURITY_PERMISSIONS_POLICY', ''):
            response.setdefault('Permissions-Policy', settings.SECURITY_PERMISSIONS_POLICY)
        return response
