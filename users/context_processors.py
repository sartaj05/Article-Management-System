from .models import Workspace
from django.conf import settings


def active_workspace(request):
    workspace = None
    if getattr(request, 'user', None) and request.user.is_authenticated:
        slug = request.headers.get('X-Workspace-Slug') or request.session.get('active_workspace_slug')
        if slug:
            workspace = Workspace.objects.filter(slug=slug, is_active=True, memberships__user=request.user).first()
    return {'active_workspace': workspace}


def demo_environment(request):
    return {'demo_mode_enabled': settings.DEMO_MODE_ENABLED}
