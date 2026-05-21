from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from apps.common.rbac import active_role_ids
from apps.events.models import EventRsvp, EventTargetGroup, EventTargetRole, EventTargetTrack, Events
from apps.groups.models import Groups, GroupMembership
from apps.users.utils.admin_scope import get_admin_track_ids, is_operational_admin


MENTOR_MEMBERSHIPS_ATTR = "_mentor_memberships"


def _get_active_memberships(user):
    # Dashboard scope follows active groups only; deleted groups are recoverable elsewhere.
    return list(
        GroupMembership.objects.select_related("group", "group__track")
        .filter(user=user, left_at__isnull=True, group__deleted_at__isnull=True)
        .order_by("id")
    )


def _prefetched_user_rsvp(event):
    user_rsvps = getattr(event, "_dashboard_user_rsvps", [])
    return user_rsvps[0] if user_rsvps else None


def _event_track_ids(event):
    track_ids = []
    if event.track_id is not None:
        track_ids.append(event.track_id)
    for target in getattr(event, "_dashboard_track_targets", []):
        if target.track_id not in track_ids:
            track_ids.append(target.track_id)
    return track_ids


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
        "track_id": event.track_id,
        "groups": [t.group_id for t in group_targets] if group_targets else [],
        "event_type": getattr(event, 'event_type', None),
        "start_datetime": event.start_datetime,
        "ends_datetime": event.ends_datetime,
        "location": event.location,
        "location_link": event.location_link,
        "event_image": getattr(event, 'event_image', None),
        "is_virtual": event.is_virtual,
        "rsvp_status": user_rsvp.rsvp_status if user_rsvp else "pending",
    }


def _match_for_admin(event, admin_track_ids):
    if admin_track_ids is None:
        return _build_payload(event)

    allowed_track_ids = set(admin_track_ids)
    track_ids = _event_track_ids(event)
    matching_group_targets = [
        target for target in _event_group_targets(event) if target.group.track_id in allowed_track_ids
    ]
    matching_track_ids = [track_id for track_id in track_ids if track_id in allowed_track_ids]
    is_platform_wide = not track_ids and not _event_group_targets(event)

    if not is_platform_wide and not matching_group_targets and not matching_track_ids:
        return None

    user_rsvp = _prefetched_user_rsvp(event)
    return _build_payload(event, user_rsvp=user_rsvp)


def _match_for_member(event, *, user_group_ids, user_track_ids, user_role_ids):
    user_rsvp = _prefetched_user_rsvp(event)
    if user_rsvp and user_rsvp.rsvp_status != EventRsvp.RsvpStatus.DECLINED:
        return _build_payload(event, user_rsvp=user_rsvp)

    track_ids = _event_track_ids(event)
    group_targets = _event_group_targets(event)
    role_ids = _event_role_ids(event)

    matching_group_targets = [target for target in group_targets if target.group_id in user_group_ids]
    matching_track_ids = [track_id for track_id in track_ids if track_id in user_track_ids]

    track_ok = not track_ids or bool(matching_track_ids)
    group_ok = not group_targets or bool(matching_group_targets)
    role_ok = not role_ids or bool(role_ids & user_role_ids)

    if not (track_ok and group_ok and role_ok):
        return None

    if user_rsvp and user_rsvp.rsvp_status == EventRsvp.RsvpStatus.DECLINED:
        return None

    return _build_payload(event, user_rsvp=user_rsvp)


def get_personalized_next_event(user):
    now = timezone.now()
    memberships = _get_active_memberships(user)
    user_group_ids = {membership.group_id for membership in memberships}
    user_track_ids = {membership.group.track_id for membership in memberships if membership.group_id}
    if user.track_id is not None:
        user_track_ids.add(user.track_id)

    user_role_ids = active_role_ids(user)
    admin_track_ids = get_admin_track_ids(user) if is_operational_admin(user) else []

    queryset = (
        Events.objects.filter(deleted_at__isnull=True, ends_datetime__gte=now)
        .select_related("track")
        .prefetch_related(
            Prefetch(
                "rsvps",
                queryset=EventRsvp.objects.filter(user=user).order_by("id"),
                to_attr="_dashboard_user_rsvps",
            ),
            Prefetch(
                "eventtargetgroup_set",
                queryset=EventTargetGroup.objects.select_related("group", "group__track").order_by("id"),
                to_attr="_dashboard_group_targets",
            ),
            Prefetch(
                "eventtargetrole_set",
                queryset=EventTargetRole.objects.select_related("role").order_by("id"),
                to_attr="_dashboard_role_targets",
            ),
            Prefetch(
                "eventtargettrack_set",
                queryset=EventTargetTrack.objects.select_related("track").order_by("id"),
                to_attr="_dashboard_track_targets",
            ),
        )
        .order_by("start_datetime", "id")
    )

    for event in queryset:
        if is_operational_admin(user):
            payload = _match_for_admin(event, admin_track_ids)
        else:
            payload = _match_for_member(
                event,
                user_group_ids=user_group_ids,
                user_track_ids=user_track_ids,
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

def get_groups_preview(*, user, mine=False, track_id=None):
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

    ``track_id`` (optional) further narrows the result to a single track.
    """
    qs = (
        Groups.objects.for_user(user, mine=mine)
        .select_related("track")
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
        .order_by("group_name", "id")
    )

    if track_id is not None:
        qs = qs.filter(track_id=track_id)

    return qs
