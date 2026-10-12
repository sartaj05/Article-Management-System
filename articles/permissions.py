from rest_framework.permissions import BasePermission


ROLE_CAPABILITIES = {
    'Journalist': frozenset({
        'article.create',
        'article.edit.own',
        'article.submit',
        'article.autosave.own',
        'article.revision.view.own',
        'article.media.manage.own',
        'analytics.view.own',
    }),
    'Editor': frozenset({
        'article.view.all',
        'article.edit.assigned',
        'article.review',
        'article.publish',
        'article.assign.view',
        'article.autosave.assigned',
        'article.revision.view.all',
        'article.media.manage.all',
        'analytics.view.all',
        'audit.view',
    }),
    'Admin': frozenset({
        'admin.*',
        'article.view.all',
        'article.edit.all',
        'article.review',
        'article.publish',
        'article.assign.manage',
        'article.revision.view.all',
        'article.media.manage.all',
        'analytics.view.all',
        'audit.view',
        'system.health.view',
    }),
}


def capabilities_for_user(user):
    """Return stable, UI-safe capability names for the current user."""

    if not getattr(user, 'is_authenticated', False):
        return frozenset()
    return ROLE_CAPABILITIES.get(getattr(user, 'role', ''), frozenset())


def user_has_capability(user, capability):
    capabilities = capabilities_for_user(user)
    return 'admin.*' in capabilities or capability in capabilities


class HasRole(BasePermission):
    """Allow a request when the authenticated user has an allowed role."""

    allowed_roles = frozenset()

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


class IsAdmin(HasRole):
    allowed_roles = frozenset({'Admin'})


class IsEditor(HasRole):
    allowed_roles = frozenset({'Editor'})


class IsJournalist(HasRole):
    allowed_roles = frozenset({'Journalist'})


class IsEditorOrAdmin(HasRole):
    allowed_roles = frozenset({'Editor', 'Admin'})


class IsJournalistEditorOrAdmin(HasRole):
    allowed_roles = frozenset({'Journalist', 'Editor', 'Admin'})


class IsOwnerOrEditorOrAdmin(BasePermission):
    """Allow article access to its author, editors, and admins."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return bool(
            obj.author_id == request.user.id
            or request.user.role in {'Editor', 'Admin'}
        )


def editor_has_capability(user, article, capability):
    if user.role == 'Admin':
        return True
    if user.role != 'Editor':
        return False
    assignments = article.assignments.all()
    if not assignments.exists():
        return True
    return assignments.filter(editor=user, **{f'can_{capability}': True}).exists()
