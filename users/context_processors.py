from .models import Workspace


def active_workspace(request):
    workspace = None
    if getattr(request, 'user', None) and request.user.is_authenticated:
        slug = request.headers.get('X-Workspace-Slug') or request.session.get('active_workspace_slug')
        if slug:
            workspace = Workspace.objects.filter(slug=slug, is_active=True, memberships__user=request.user).first()
    return {'active_workspace': workspace}
