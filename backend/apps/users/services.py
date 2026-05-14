from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from apps.events.models import Events
from apps.groups.models import GroupMembership, Groups
from apps.matching_runtime.models import MatchRecommendation

from .models import User
from .utils.admin_scope import get_admin_track_ids


def get_operational_admin_summary(user):
    """Counts that drive the admin dashboard.

    Track-scoped admins see only their tracks (plus untargeted events,
    which reach everyone). Global admins see everything.

    Caller is expected to have already gated via ``is_operational_admin``.
    """
    track_scope = get_admin_track_ids(user)

    user_qs = User.objects.all()
    group_qs = Groups.objects.filter(deleted_at__isnull=True)
    rec_qs = MatchRecommendation.objects.filter(accepted=False)
    event_qs = Events.objects.filter(
        deleted_at__isnull=True,
        start_datetime__gte=timezone.now(),
    )

    if track_scope is not None:
        user_qs = user_qs.filter(track_id__in=track_scope)
        group_qs = group_qs.filter(track_id__in=track_scope)
        rec_qs = rec_qs.filter(group__track_id__in=track_scope)
        event_qs = event_qs.filter(Q(track_id__in=track_scope) | Q(track__isnull=True))

    # Single aggregate per queryset — collapses what used to be 7 SELECT
    # COUNT(*) round-trips into 3 (users, groups, recs+events stay separate
    # since events isn't track-aliased the same way).
    user_counts = user_qs.aggregate(
        active=Count("id", filter=Q(account_status=User.AccountStatus.ACTIVE)),
        invited_or_pending=Count("id", filter=Q(
            account_status__in=[User.AccountStatus.INVITED, User.AccountStatus.PENDING]
        )),
        suspended_or_deactivated=Count("id", filter=Q(
            account_status__in=[User.AccountStatus.SUSPENDED, User.AccountStatus.DEACTIVATED]
        )),
    )

    has_active_mentor = Exists(
        GroupMembership.objects.filter(
            group=OuterRef("pk"),
            membership_role__iexact="mentor",
            left_at__isnull=True,
        )
    )
    group_counts = group_qs.annotate(_has_mentor=has_active_mentor).aggregate(
        total=Count("id"),
        without_mentor=Count("id", filter=Q(_has_mentor=False)),
    )

    # MatchRecommendation only has an `accepted` flag — no declined/expired
    # state. Restrict to groups that still need a mentor so resolved or
    # stale recommendations stop inflating the "needs review" count.
    mentorless_group_ids = group_qs.annotate(_m=has_active_mentor).filter(
        _m=False
    ).values_list("id", flat=True)

    return {
        "track_scope": [] if track_scope is None else list(track_scope),
        "active_users": user_counts["active"],
        "invited_or_pending_users": user_counts["invited_or_pending"],
        "suspended_or_deactivated_users": user_counts["suspended_or_deactivated"],
        "active_groups": group_counts["total"],
        "groups_without_mentor": group_counts["without_mentor"],
        "unassigned_match_recommendations": rec_qs.filter(group_id__in=mentorless_group_ids).count(),
        "upcoming_events": event_qs.count(),
    }
