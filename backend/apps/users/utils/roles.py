
from django.utils import timezone
from django.db.models import Q
from apps.resources.models import RoleAssignmentHistory

def get_active_assignment(user):
    """
    Return the user's active RoleAssignmentHistory for business roles.
    
    A role is active if:
      - valid_from <= now AND
      - (valid_to >= now OR valid_to IS NULL) AND
      - role is not deleted (role__isnull=False)
    
    Handles both time-bound roles and indefinite roles (NULL valid_to).
    Excludes assignments where the role has been deleted.
    """
    now = timezone.now()
    return (
        RoleAssignmentHistory.objects
        .select_related("role")
        .filter(user=user, valid_from__lte=now)
        .filter(Q(valid_to__gte=now) | Q(valid_to__isnull=True))
        .exclude(role__isnull=True)  # Exclude deleted roles
        .order_by("-valid_from")
        .first()
    )
