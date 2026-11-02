"""Request-time workspace resolution and tenant queryset helpers."""

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from users.models import Workspace


WORKSPACE_HEADER = 'X-Workspace-Slug'


def requested_workspace_slug(request):
    return request.headers.get(WORKSPACE_HEADER) or request.session.get('active_workspace_slug')


def resolve_workspace(request, *, strict=True):
    """Attach the selected workspace to a request after authentication.

    A workspace can only be selected by an owner or a current member. The
    helper is deliberately called from both middleware and DRF views because
    JWT authentication happens inside DRF, after Django middleware runs.
    """
    slug = requested_workspace_slug(request)
    if not slug:
        request.workspace = None
        return None
    if not getattr(request.user, 'is_authenticated', False):
        if strict:
            raise PermissionDenied('Authentication is required to select a workspace.')
        request.workspace = None
        return None
    workspace = Workspace.objects.filter(
        Q(owner=request.user) | Q(memberships__user=request.user),
        slug=slug,
        is_active=True,
    ).distinct().first()
    if workspace is None:
        raise PermissionDenied('You are not a member of this workspace.')
    request.workspace = workspace
    return workspace


def workspace_member_ids(request):
    """Return workspace IDs visible to the authenticated request user."""
    if not getattr(request.user, 'is_authenticated', False):
        return Workspace.objects.none().values('id')
    return Workspace.objects.filter(
        Q(owner=request.user) | Q(memberships__user=request.user),
        is_active=True,
    ).distinct().values('id')


def scope_queryset(queryset, request, relation='workspace'):
    """Scope a queryset when a workspace is explicitly selected.

    Existing records without a workspace remain available for backwards
    compatibility when no workspace is selected. Once a tenant is selected,
    only records linked to that tenant are returned.
    """
    workspace = getattr(request, 'workspace', None)
    if workspace is None:
        return queryset
    return queryset.filter(**{relation: workspace})


class WorkspaceScopeMixin:
    """DRF mixin that resolves workspace context after JWT/session auth."""

    def initial(self, request, *args, **kwargs):
        response = super().initial(request, *args, **kwargs)
        resolve_workspace(request)
        return response
