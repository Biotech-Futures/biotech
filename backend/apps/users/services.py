from django.db.models import Count, Q
from django.utils import timezone

from apps.events.models import Events
from apps.groups.models import Groups
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

    mentorless_group_ids = group_qs.annotate(
        active_mentor_count=Count(
            "groupmembership",
            filter=Q(
                groupmembership__membership_role__iexact="mentor",
                groupmembership__left_at__isnull=True,
            ),
        )
    ).filter(active_mentor_count=0).values_list("id", flat=True)

    # MatchRecommendation only has an `accepted` flag — no declined/expired
    # state. Restrict to groups that still need a mentor so resolved or
    # stale recommendations stop inflating the "needs review" count.
    actionable_recs = rec_qs.filter(group_id__in=mentorless_group_ids)

    return {
        "track_scope": [] if track_scope is None else list(track_scope),
        "active_users": user_qs.filter(account_status=User.AccountStatus.ACTIVE).count(),
        "invited_or_pending_users": user_qs.filter(
            account_status__in=[User.AccountStatus.INVITED, User.AccountStatus.PENDING]
        ).count(),
        "suspended_or_deactivated_users": user_qs.filter(
            account_status__in=[User.AccountStatus.SUSPENDED, User.AccountStatus.DEACTIVATED]
        ).count(),
        "active_groups": group_qs.count(),
        "groups_without_mentor": mentorless_group_ids.count(),
        "unassigned_match_recommendations": actionable_recs.count(),
        "upcoming_events": event_qs.count(),
    }
