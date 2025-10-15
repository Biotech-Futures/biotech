
from django.utils import timezone
from apps.resources.models import RoleAssignmentHistory

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
