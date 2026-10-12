from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Protect browser-rendered workspace pages by authenticated role."""

    allowed_roles = frozenset(roles)

    def decorator(view):
        @login_required(login_url='/login-template/')
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                raise PermissionDenied('You do not have access to this workspace.')
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
