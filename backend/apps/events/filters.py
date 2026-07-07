"""Filters for GET /api/v1/events/."""

import django_filters
from django.db.models import Exists, OuterRef, Q

from apps.common.rbac import is_admin

from .models import (
    EventRsvp,
    EventTargetGroup,
    Events,
)


class EventFilter(django_filters.FilterSet):
    """Query params for GET /api/v1/events/.

    * `rsvp_status=accepted` (or `accepted,tentative`) — filter by the
      caller's RSVP status. Single or comma-separated.
    * `category=workshop` — case-insensitive `event_type` match.
    * `user=<id>` — events the given user has any RSVP on. Self always
      allowed; admins may audit anyone; supervisors may audit their
      supervisees and the mentors of those supervisees' groups.
    * `group=<id>` — events targeting the given group. Members and
      admins may query; supervisors may query groups containing any of
      their supervisees.

    Each id filter returns an empty queryset (rather than 403) when
    the caller may not query the requested id, so unauthorised tries
    silently degrade and cannot widen the visible set.
    """

    rsvp_status = django_filters.BaseInFilter(method="filter_rsvp_status")
    category = django_filters.CharFilter(field_name="event_type", lookup_expr="iexact")
    user = django_filters.NumberFilter(method="filter_user")
    group = django_filters.NumberFilter(method="filter_group")

    class Meta:
        model = Events
        fields = ["rsvp_status", "category", "user", "group"]

    _VALID_STATUSES = frozenset(EventRsvp.RsvpStatus.values)

    def _caller(self):
        request = getattr(self, "request", None)
        return getattr(request, "user", None) if request is not None else None

    def filter_rsvp_status(self, queryset, name, values):
        caller = self._caller()
        if caller is None or not caller.is_authenticated:
            return queryset.none()
        statuses = [v for v in (values or []) if v in self._VALID_STATUSES]
        if not statuses:
            return queryset.none()
        explicit_event_ids = EventRsvp.objects.filter(
            user=caller, rsvp_status__in=statuses
        ).values_list("event_id", flat=True)
        # `pending` is treated as "not responded yet" — admin invites
        # default to PENDING, and an event the caller has never touched
        # is functionally the same state. Include both.
        if EventRsvp.RsvpStatus.PENDING in statuses:
            no_row_for_caller = ~Exists(
                EventRsvp.objects.filter(event_id=OuterRef("id"), user=caller)
            )
            return queryset.filter(Q(id__in=explicit_event_ids) | no_row_for_caller)
        return queryset.filter(id__in=explicit_event_ids)

    def filter_user(self, queryset, name, user_id):
        caller = self._caller()
        if caller is None or not caller.is_authenticated:
            return queryset.none()
        if not _can_caller_query_user(caller, user_id):
            return queryset.none()
        event_ids = EventRsvp.objects.filter(user_id=user_id).values_list(
            "event_id", flat=True
        )
        return queryset.filter(id__in=event_ids)

    def filter_group(self, queryset, name, group_id):
        caller = self._caller()
        if caller is None or not caller.is_authenticated:
            return queryset.none()
        if not _can_caller_query_group(caller, group_id):
            return queryset.none()
        # An event is "for this group" if it carries an EventTargetGroup
        # row pointing at it.
        return queryset.filter(
            Exists(
                EventTargetGroup.objects.filter(
                    event_id=OuterRef("id"), group_id=group_id
                )
            )
        )

# ---------------------------------------------------------------------------
# Permission helpers for the scoped id filters.
#
# Supervisor scope: a supervisor may inspect their supervisees' RSVPs and
# the RSVPs of mentors in those supervisees' groups. Implemented here as
# small helpers rather than reaching into apps.tasks.permissions to avoid
# cross-app coupling.
# ---------------------------------------------------------------------------


def _supervisee_user_ids(caller):
    """User ids of students this caller supervises (primary supervisor only)."""
    from apps.users.models import StudentProfile

    return list(
        StudentProfile.objects.filter(supervisor_id=caller.id)
        .values_list("user_id", flat=True)
    )


def _supervisor_group_ids(caller, supervisee_ids):
    if not supervisee_ids:
        return []
    from apps.groups.models import GroupMembership

    return list(
        GroupMembership.objects.filter(
            user_id__in=supervisee_ids, left_at__isnull=True
        ).values_list("group_id", flat=True).distinct()
    )


def _supervisor_visible_user_ids(caller):
    """Set of user ids the caller may inspect via ?user=<id>:
    self ∪ supervisees ∪ mentors of supervisees' groups."""
    visible = {caller.id}
    supervisee_ids = _supervisee_user_ids(caller)
    if not supervisee_ids:
        return visible
    visible.update(supervisee_ids)

    from apps.groups.models import GroupMembership

    group_ids = _supervisor_group_ids(caller, supervisee_ids)
    if group_ids:
        mentor_ids = GroupMembership.objects.filter(
            group_id__in=group_ids,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
            left_at__isnull=True,
        ).values_list("user_id", flat=True)
        visible.update(mentor_ids)
    return visible


def _can_caller_query_user(caller, user_id) -> bool:
    if is_admin(caller):
        return True
    return user_id in _supervisor_visible_user_ids(caller)


def _can_caller_query_group(caller, group_id) -> bool:
    """Admin, active member, or supervisor of any member of the group."""
    if is_admin(caller):
        return True

    from apps.groups.models import GroupMembership

    if GroupMembership.objects.filter(
        user=caller, group_id=group_id, left_at__isnull=True
    ).exists():
        return True

    supervisee_ids = _supervisee_user_ids(caller)
    if supervisee_ids and GroupMembership.objects.filter(
        group_id=group_id, user_id__in=supervisee_ids, left_at__isnull=True
    ).exists():
        return True

    return False
