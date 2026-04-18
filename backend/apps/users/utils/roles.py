
from django.db.models import Q
from django.utils import timezone

from apps.resources.models import RoleAssignmentHistory


def get_active_assignment(user):
    """
    Active assignment: valid_from <= now and (valid_to is null or valid_to >= now).
    """
    now = timezone.now()
    return (
        RoleAssignmentHistory.objects.select_related("role")
        .filter(user=user, valid_from__lte=now)
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
        .order_by("-valid_from")
        .first()
    )
