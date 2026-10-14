"""Who may join a team's live submission room: whoever may open its entry."""
from apps.groups.models import Groups
from config.errors import GroupAccessDenied

from .views import _require_can_view


def can_join(user, group_id: int) -> bool:
    if not Groups.objects.filter(pk=group_id, deleted_at__isnull=True).exists():
        return False
    try:
        _require_can_view(user, group_id)
    except GroupAccessDenied:
        return False
    return True
