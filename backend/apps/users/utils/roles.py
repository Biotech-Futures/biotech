
from django.utils import timezone
from apps.resources.models import RoleAssignmentHistory
from rest_framework.permissions import BasePermission

def get_active_assignment(user):
    """
    Return the user's active RoleAssignmentHistory using the
    exact same validity pattern as UserSerializer._active_assignment():
      valid_from <= now AND valid_to >= now
    """
    now = timezone.now()
    return (
        RoleAssignmentHistory.objects
        .select_related("role")
        .filter(user=user, valid_from__lte=now, valid_to__gte=now)
        .order_by("-valid_from")
        .first()
    )

ADMIN_OR_SUPERVISOR_ROLE_IDS = {1, 2}

# We'll use this for admin/superviser specific requests for W3

class IsAdminOrSupervisor(BasePermission):
    """
    Allow is_staff or active RoleAssignmentHistory with role_id in {1,2}.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff:
            return True

        try:
            from apps.resources.models import RoleAssignmentHistory
        except Exception:
            return False

        now = timezone.now()
        return RoleAssignmentHistory.objects.filter(
            user=user,
            role_id__in=ADMIN_OR_SUPERVISOR_ROLE_IDS,
            valid_from__lte=now,
            valid_to__gte=now,
        ).exists()