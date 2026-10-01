from rest_framework.authentication import get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.authentication import TokenAuthentication

class CustomTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # List of public paths that don't require authentication
        self.public_endpoints = [
            '/api/login-template/',  # Example public endpoint
            '/api/login/',  # Example public endpoint
            '/api/register/',  # Example public endpoint
           
            '/',  # Skip root URL
        ]

    def __call__(self, request):
        # Skip authentication for any public endpoints
        for endpoint in self.public_endpoints:
            if request.path_info.startswith(endpoint):
                return self.get_response(request)

        # Skip authentication for Django admin routes
        if request.path_info.startswith('/admin/'):
            return self.get_response(request)

        # Proceed with token authentication for other requests
        token = get_authorization_header(request).split()
        if not token or len(token) != 2:
            raise AuthenticationFailed('Authorization credentials were not provided.')

        token = token[1]
        
        try:
            user, auth = TokenAuthentication().authenticate_credentials(token)
        except AuthenticationFailed:
            raise AuthenticationFailed('Invalid or expired token.')
        
        request.user = user  # Attach the user to the request
        return self.get_response(request)
