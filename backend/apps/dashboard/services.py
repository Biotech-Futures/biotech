from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from apps.common.rbac import active_role_ids
from apps.events.models import EventRsvp, EventTargetGroup, EventTargetRole, Events
from apps.groups.models import Groups, GroupMembership, group_name_sort_key
from apps.common.rbac import is_admin


MENTOR_MEMBERSHIPS_ATTR = "_mentor_memberships"


def _get_active_memberships(user):
    # Dashboard scope follows active groups only; deleted groups are recoverable elsewhere.
    return list(
        GroupMembership.objects.select_related("group")
        .filter(user=user, left_at__isnull=True, group__deleted_at__isnull=True)
        .order_by("id")
    )


def _prefetched_user_rsvp(event):
    user_rsvps = getattr(event, "_dashboard_user_rsvps", [])
    return user_rsvps[0] if user_rsvps else None


def _event_group_targets(event):
    return list(getattr(event, "_dashboard_group_targets", []))


def _event_role_ids(event):
    return {target.role_id for target in getattr(event, "_dashboard_role_targets", [])}


def _build_payload(event, user_rsvp=None):
    group_targets = _event_group_targets(event)

    return {
        "id": event.id,
        "event_name": event.event_name,
        "event_description": getattr(event, 'description', None),
        "groups": [t.group_id for t in group_targets] if group_targets else [],
        "event_type": getattr(event, 'event_type', None),
        "start_datetime": event.start_datetime,
        "ends_datetime": event.ends_datetime,
        "location": event.location,
        "location_link": event.location_link,
        "event_image": getattr(event, 'event_image', None),
        "event_format": event.event_format,
        "rsvp_status": user_rsvp.rsvp_status if user_rsvp else "pending",
    }


def _match_for_admin(event):
    user_rsvp = _prefetched_user_rsvp(event)
    return _build_payload(event, user_rsvp=user_rsvp)


def _match_for_member(event, *, user_group_ids, user_role_ids):
    user_rsvp = _prefetched_user_rsvp(event)
    if user_rsvp and user_rsvp.rsvp_status != EventRsvp.RsvpStatus.DECLINED:
        return _build_payload(event, user_rsvp=user_rsvp)

    group_targets = _event_group_targets(event)
    role_ids = _event_role_ids(event)

    matching_group_targets = [target for target in group_targets if target.group_id in user_group_ids]

    group_ok = not group_targets or bool(matching_group_targets)
    role_ok = not role_ids or bool(role_ids & user_role_ids)

    if not (group_ok and role_ok):
        return None

    if user_rsvp and user_rsvp.rsvp_status == EventRsvp.RsvpStatus.DECLINED:
        return None

    return _build_payload(event, user_rsvp=user_rsvp)


def get_personalized_next_event(user):
    now = timezone.now()
    memberships = _get_active_memberships(user)
    user_group_ids = {membership.group_id for membership in memberships}

    user_role_ids = active_role_ids(user)
    caller_is_admin = is_admin(user)

    queryset = (
        Events.objects.filter(deleted_at__isnull=True, ends_datetime__gte=now)
        .prefetch_related(
            Prefetch(
                "rsvps",
                queryset=EventRsvp.objects.filter(user=user).order_by("id"),
                to_attr="_dashboard_user_rsvps",
            ),
            Prefetch(
                "eventtargetgroup_set",
                queryset=EventTargetGroup.objects.select_related("group").order_by("id"),
                to_attr="_dashboard_group_targets",
            ),
            Prefetch(
                "eventtargetrole_set",
                queryset=EventTargetRole.objects.select_related("role").order_by("id"),
                to_attr="_dashboard_role_targets",
            ),
        )
        .order_by("start_datetime", "id")
    )

    for event in queryset:
        if caller_is_admin:
            payload = _match_for_admin(event)
        else:
            payload = _match_for_member(
                event,
                user_group_ids=user_group_ids,
                user_role_ids=user_role_ids,
            )
        if payload is not None:
            return payload

    return None


def get_dashboard_summary(user):
    """
    All dashboard business logic lives here.
    Views must never compute data directly.
    """
    user_identifier = getattr(user, "username", None) or user.email

    return {
        "user": user_identifier,
        "stats": {
            "tasks": 0,
            "events": 0,
            "groups": 0,
        }
    }

def get_groups_preview(*, user, mine=False):
    """
    Returns an annotated queryset of active groups scoped to the user.

    Scoping is delegated to ``Groups.objects.for_user(user, mine=mine)``
    so every consumer that needs "groups visible to this user" shares
    one canonical implementation (DRY querysets). This service then
    layers on the dashboard-specific projection: ``member_count``
    annotation + a ``Prefetch`` that materialises mentor memberships
    onto ``MENTOR_MEMBERSHIPS_ATTR``, so the caller can hand the
    queryset directly to ``DashboardGroupPreviewSerializer`` without
    iterating in Python.

    """
    qs = (
        Groups.objects.for_user(user, mine=mine)
        .annotate(
            member_count=Count(
                "groupmembership",
                filter=Q(groupmembership__left_at__isnull=True),
            )
        )
        .prefetch_related(
            Prefetch(
                "groupmembership_set",
                queryset=GroupMembership.objects.filter(
                    membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
                    left_at__isnull=True,
                )
                .select_related("user")
                .order_by("id"),
                to_attr=MENTOR_MEMBERSHIPS_ATTR,
            )
        )
        # Order on the padded key: raw group_name would sort "BTF10" before "BTF9".
        .annotate(group_name_key=group_name_sort_key())
        .order_by("group_name_key", "id")
    )

    return qs
