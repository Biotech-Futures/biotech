"""
Custom permission classes shared across the project.
"""

from rest_framework.permissions import BasePermission


class IsPlatformAdmin(BasePermission):
    """
    Allows access only to authenticated users with the platform admin role.

    We treat both Django superusers and application-level admins (role == "admin")
    as platform administrators.
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return getattr(user, "role", None) == "admin"
