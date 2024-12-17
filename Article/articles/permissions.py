from rest_framework.permissions import BasePermission

class IsEditorOrAdmin(BasePermission):
    """
    Custom permission to grant access only to Editors and Admins.
    """
    def has_permission(self, request, view):
        return request.user.role in ['Editor', 'Admin']

class IsJournalist(BasePermission):
    """
    Custom permission to grant access only to Journalists.
    """
    def has_permission(self, request, view):
        return request.user.role == 'Journalist'
