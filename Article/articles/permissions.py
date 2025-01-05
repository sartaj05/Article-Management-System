from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    """
    Permission to grant access only to Admin users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Admin'


class IsEditor(BasePermission):
    """
    Permission to grant access only to Editor users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Editor'


class IsJournalist(BasePermission):
    """
    Permission to grant access only to Journalist users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Journalist'


class IsEditorOrAdmin(BasePermission):
    """
    Permission to grant access to both Editors and Admins.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['Editor', 'Admin']


class IsOwnerOrAdmin(BasePermission):
    """
    Permission to allow access to the resource's owner or an Admin user.
    """
    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and (
            obj.author == request.user or request.user.role == 'Admin'
        )
    
from rest_framework import permissions

class IsEditorOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        # Allow access to Editors and Admins only
        return request.user and (request.user.role == 'Editor' or request.user.is_staff)

