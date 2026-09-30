from rest_framework.permissions import BasePermission

from apps.users.models import AdminScope


class IsGrader(BasePermission):
    """Any admin may grade: staff, superuser, or platform admin (AdminScope row)."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_staff or user.is_superuser:
            return True
        return AdminScope.objects.filter(user=user).exists()
