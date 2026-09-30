from rest_framework.permissions import BasePermission


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
