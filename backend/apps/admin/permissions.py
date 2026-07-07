from rest_framework.permissions import BasePermission

from apps.users.models import AdminScope


class IsAdminScoped(BasePermission):
    """Allow access only to users with an AdminScope entry (i.e. admins)."""

    message = "You do not have admin privileges."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return AdminScope.objects.filter(user=request.user).exists()
