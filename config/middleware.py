import uuid


class RequestIDMiddleware:
    """Attach a stable correlation ID to every response and request log context."""

    header_name = 'X-Request-ID'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get(self.header_name) or uuid.uuid4().hex
        response = self.get_response(request)
        response[self.header_name] = request.request_id
        return response
