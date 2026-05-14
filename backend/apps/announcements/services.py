from django.db.models import Q
from django.utils import timezone

from apps.groups.models import GroupMembership
from apps.resources.models import RoleAssignmentHistory

from .models import Announcement


def visible_announcements_queryset(user, *, include_archived=False):
    """Active announcements the user is allowed to read.

    Mirrors the visibility rules used by the announcements list endpoint
    so the dashboard summary and the list view never drift.

    Anonymous users see nothing; global staff see every row (callers may
    drop ``include_archived`` if they want to hide archived rows from
    admins too — e.g. the dashboard "unread" count).
    """
    base = Announcement.objects.all()
    if not include_archived:
        base = base.filter(archived_at__isnull=True)

    if not user or not user.is_authenticated:
        return Announcement.objects.none()

    if user.is_staff or user.is_superuser:
        return base

    now = timezone.now()
    role_ids = RoleAssignmentHistory.objects.filter(
        user=user,
        valid_from__lte=now,
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now)
    ).values_list("role_id", flat=True)

    audience_filter = Q(author_user=user) | Q(visibility_scope=Announcement.VisibilityScope.PUBLIC)
    if role_ids:
        audience_filter |= Q(audiences__role_id__in=role_ids)
    if user.track_id:
        audience_filter |= Q(track_id=user.track_id) | Q(audiences__track_id=user.track_id)

    group_ids = list(
        GroupMembership.objects.filter(user=user, left_at__isnull=True)
        .values_list("group_id", flat=True)
    )
    if group_ids:
        audience_filter |= Q(audiences__group_id__in=group_ids)

    # Non-admin viewers never see archived rows regardless of caller flag.
    return base.filter(archived_at__isnull=True).filter(audience_filter).distinct()
