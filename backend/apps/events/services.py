"""Business logic for the events app.

Keeping query and registration mechanics here (rather than inside views)
maintains the project's "no fat views" rule: ``views.py`` should only
parse the request, enforce permissions, and shape the response.

The single source of truth for "is this user a target of this event?"
lives in :func:`can_user_rsvp_to_event`. Both the FE-facing register
shortcut (``POST .../register/``) and the full RSVP endpoint
(``POST .../rsvp/``) gate writes through it, so the role-permission
contract — "admins push events, users RSVP" — has exactly one
implementation that needs to change if the rule changes.
"""

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.users.utils.admin_scope import (
    get_admin_track_ids,
    is_operational_admin,
)

from .models import (
    EventRsvp,
    EventTargetGroup,
    EventTargetRole,
    EventTargetTrack,
    Events,
)


def get_user_registered_event_ids(user):
    """Return a ``set`` of event ids ``user`` has *registered* for.

    "Registered" is defined narrowly as ``rsvp_status == GOING`` — the
    user has actively committed to attending. PENDING / MAYBE / DECLINED
    all serialize as ``registered: false``. This is the single source
    of truth used by both the per-row ``EventSerializer.registered``
    field and the ``?registered=true`` / ``?mine=true`` filters, so any
    future contract change happens in exactly one place.

    The 4-value ``RsvpStatus`` enum stays the canonical record of
    *intent*; ``registered`` is a derived projection of "going".

    Returning a ``set`` keeps O(1) membership checks for the serializer
    so listing N events stays O(N) without an N+1 query against
    ``EventRsvp``.
    """
    if not user or not user.is_authenticated:
        return set()
    return set(
        EventRsvp.objects.filter(
            user=user,
            rsvp_status=EventRsvp.RsvpStatus.GOING,
        ).values_list("event_id", flat=True)
    )


# ---------------------------------------------------------------------------
# Visibility gate.
# ---------------------------------------------------------------------------

def can_user_rsvp_to_event(user, event) -> bool:
    """Return True iff ``user`` is a legitimate target of ``event``.

    Mirrors the role-permission model:

    * **Global admins** (``is_staff`` / ``is_superuser`` /
      ``AdminScope.is_global``) can RSVP to anything.
    * **Track admins** are restricted to events within their assigned
      tracks — events whose direct ``track`` FK, ``EventTargetTrack``
      rows, or ``EventTargetGroup``'s parent track is in their scope
      — plus untargeted (platform-wide) events.
    * **Explicit invitees** (any existing ``EventRsvp`` row for this
      ``(event, user)`` pair) can always change their state. This is
      what makes "decline → I changed my mind, going" work without
      the user losing access the moment they decline.
    * **Untargeted events** (no track / no group / no role targeting
      on the event) are open to every authenticated user — same as a
      platform-wide announcement.
    * **Targeted events** require the user's scope to intersect every
      *present* targeting axis (AND across axes, OR within an axis).

    The "AND across axes, OR within axis" rule mirrors the dashboard's
    next-event ``_is_member_match`` so the two surfaces (read vs.
    write) agree on who is "a target". Diverging would mean a user
    could see an event in their next-event card but be told "403"
    when they click Register — the worst kind of inconsistency.

    Pure / side-effect-free / unit-testable in isolation.
    """
    if not user or not user.is_authenticated:
        return False

    target_track_ids = _event_target_track_ids(event)
    target_group_ids = _event_target_group_ids(event)
    target_role_ids = _event_target_role_ids(event)
    is_untargeted = (
        not target_track_ids and not target_group_ids and not target_role_ids
    )

    # Operational admins. Global admins (admin_track_ids is None)
    # bypass entirely; track admins must be scoped to a track the
    # event touches OR the event must be untargeted (platform-wide
    # announcements stay visible org-wide regardless of a track
    # admin's narrow scope).
    if is_operational_admin(user):
        admin_track_ids = get_admin_track_ids(user)
        if admin_track_ids is None:
            return True
        if is_untargeted:
            return True
        admin_track_ids_set = set(admin_track_ids)
        # Tracks reachable through any of the event's targeting axes.
        event_admin_relevant_tracks = set(target_track_ids) | {
            target.group.track_id
            for target in EventTargetGroup.objects.filter(event=event).select_related("group")
        }
        return bool(admin_track_ids_set & event_admin_relevant_tracks)

    # Explicit invite — admin already named this user. Includes the
    # ``DECLINED`` case on purpose: a declined invite must remain
    # actionable so the user can flip back to going / maybe.
    if EventRsvp.objects.filter(event=event, user=user).exists():
        return True

    # Untargeted event = platform-wide announcement, open to all.
    if is_untargeted:
        return True

    user_group_ids, user_track_ids, user_role_ids = _user_scope(user)

    # AND across axes, OR within an axis. An axis with no targets is a
    # free pass on that axis (matches dashboard's _is_member_match).
    track_ok = (not target_track_ids) or bool(target_track_ids & user_track_ids)
    group_ok = (not target_group_ids) or bool(target_group_ids & user_group_ids)
    role_ok = (not target_role_ids) or bool(target_role_ids & user_role_ids)
    return track_ok and group_ok and role_ok


# ---------------------------------------------------------------------------
# Read-side scoping: ``GET /events/v1/`` filters to events the requesting
# user is permitted to *see*, mirroring the write-side gate above.
# ---------------------------------------------------------------------------


def visible_events_queryset(user, base_qs):
    """Return ``base_qs`` filtered to events visible to ``user``.

    The read-side counterpart to :func:`can_user_rsvp_to_event` — the
    same role-model rules expressed as a queryset filter so DRF's
    pagination, search, and ordering keep operating at the DB layer.

    Visibility rules (mirror the gate, expressed in SQL):

    * **Anonymous** → only untargeted (platform-wide) events. Keeps
      the public Events page working for unauthenticated visitors
      without leaking targeted internal events.
    * **Global admin** → everything in ``base_qs``.
    * **Track admin** → events whose targeting touches their tracks
      (direct FK, ``EventTargetTrack``, or ``EventTargetGroup``'s
      parent track) ∪ untargeted events.
    * **Authenticated non-admin** → events they're explicitly invited
      to (any RSVP status) ∪ untargeted events ∪ events whose
      targeting axes intersect their scope (AND across axes, OR
      within an axis).

    Implemented with ``Exists`` subqueries instead of joins, so we
    avoid the row-multiplication / ``DISTINCT`` headache that
    multi-axis ``EventTarget*`` joins would cause.
    """
    has_track_target = Exists(
        EventTargetTrack.objects.filter(event_id=OuterRef("id"))
    )
    has_group_target = Exists(
        EventTargetGroup.objects.filter(event_id=OuterRef("id"))
    )
    has_role_target = Exists(
        EventTargetRole.objects.filter(event_id=OuterRef("id"))
    )

    untargeted_q = Q(track__isnull=True) & ~has_track_target & ~has_group_target & ~has_role_target

    if not user or not user.is_authenticated:
        return base_qs.filter(untargeted_q)

    if is_operational_admin(user):
        admin_track_ids = get_admin_track_ids(user)
        if admin_track_ids is None:
            return base_qs

        admin_track_ids = list(admin_track_ids)
        in_admin_scope = (
            Q(track_id__in=admin_track_ids)
            | Exists(
                EventTargetTrack.objects.filter(
                    event_id=OuterRef("id"),
                    track_id__in=admin_track_ids,
                )
            )
            | Exists(
                EventTargetGroup.objects.filter(
                    event_id=OuterRef("id"),
                    group__track_id__in=admin_track_ids,
                )
            )
        )
        return base_qs.filter(in_admin_scope | untargeted_q)

    # Authenticated non-admin: invited ∪ untargeted ∪ targeting match.
    user_group_ids, user_track_ids, user_role_ids = _user_scope(user)

    invited_event_ids = EventRsvp.objects.filter(user=user).values("event_id")

    # AND across axes / OR within axis, expressed via Exists.
    track_axis_pass = (Q(track__isnull=True) & ~has_track_target) | (
        Q(track_id__in=list(user_track_ids))
        | Exists(
            EventTargetTrack.objects.filter(
                event_id=OuterRef("id"),
                track_id__in=list(user_track_ids),
            )
        )
    )
    group_axis_pass = ~has_group_target | Exists(
        EventTargetGroup.objects.filter(
            event_id=OuterRef("id"),
            group_id__in=list(user_group_ids),
        )
    )
    role_axis_pass = ~has_role_target | Exists(
        EventTargetRole.objects.filter(
            event_id=OuterRef("id"),
            role_id__in=list(user_role_ids),
        )
    )

    return base_qs.filter(
        Q(id__in=invited_event_ids)
        | (track_axis_pass & group_axis_pass & role_axis_pass)
    )


def _event_target_track_ids(event) -> set:
    """Tracks the event targets — the direct ``event.track`` FK plus
    every ``EventTargetTrack`` row. Returned as a ``set`` so the gate
    can intersect cheaply.
    """
    track_ids = set()
    if event.track_id is not None:
        track_ids.add(event.track_id)
    track_ids.update(
        EventTargetTrack.objects.filter(event=event).values_list("track_id", flat=True)
    )
    return track_ids


def _event_target_group_ids(event) -> set:
    return set(
        EventTargetGroup.objects.filter(event=event).values_list("group_id", flat=True)
    )


def _event_target_role_ids(event) -> set:
    return set(
        EventTargetRole.objects.filter(event=event).values_list("role_id", flat=True)
    )


def _user_scope(user):
    """Materialise ``(group_ids, track_ids, role_ids)`` for ``user``.

    A user's track scope is the union of:
      - tracks of the groups they're an active member of, plus
      - their own ``user.track_id`` (if the User model carries one).

    Done here rather than inline in :func:`can_user_rsvp_to_event` so
    each axis is one unambiguous query and the gate function reads as
    pure boolean logic.
    """
    from apps.groups.models import GroupMembership
    from apps.resources.models import RoleAssignmentHistory

    memberships = list(
        GroupMembership.objects.filter(user=user, left_at__isnull=True)
        .select_related("group")
    )
    user_group_ids = {m.group_id for m in memberships}
    user_track_ids = {m.group.track_id for m in memberships if m.group_id}
    user_track_id = getattr(user, "track_id", None)
    if user_track_id is not None:
        user_track_ids.add(user_track_id)

    now = timezone.now()
    from django.db.models import Q

    user_role_ids = set(
        RoleAssignmentHistory.objects.filter(user=user, valid_from__lte=now)
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
        .values_list("role_id", flat=True)
    )
    return user_group_ids, user_track_ids, user_role_ids


# ---------------------------------------------------------------------------
# RSVP mutators — the single write path through which both
# ``/register/`` and ``/rsvp/`` flow.
# ---------------------------------------------------------------------------

# RSVP statuses a *user* may submit for themselves. ``PENDING`` is
# excluded on purpose: PENDING is the state the admin's invite flow
# leaves an RSVP in until the user responds. The user's own action
# always carries an opinion (going / maybe / declined).
USER_SUBMITTABLE_RSVP_STATUSES = (
    EventRsvp.RsvpStatus.GOING,
    EventRsvp.RsvpStatus.MAYBE,
    EventRsvp.RsvpStatus.DECLINED,
)


def set_user_rsvp(user, event_id, rsvp_status):
    """Set ``user``'s RSVP on event ``event_id`` to ``rsvp_status``.

    Returns ``(event, rsvp, created)``:
      - ``event``  : resolved ``Events`` instance.
      - ``rsvp``   : persisted ``EventRsvp`` row.
      - ``created``: ``True`` iff a new RSVP row was inserted by this
                     call (vs. updating an existing one).

    Raises:
      - :class:`rest_framework.exceptions.NotFound` if the event is
        missing or soft-deleted.
      - :class:`rest_framework.exceptions.ValidationError` if the
        event has already ended, or if ``rsvp_status`` is not one a
        user is allowed to set themselves.
      - :class:`rest_framework.exceptions.PermissionDenied` if the
        user is not a legitimate target of the event (per
        :func:`can_user_rsvp_to_event`).

    All write paths funnel through here so the visibility gate cannot
    be bypassed by adding a new endpoint that forgets to call it.
    """
    if rsvp_status not in USER_SUBMITTABLE_RSVP_STATUSES:
        raise ValidationError(
            {"rsvp_status": "Must be one of: going, maybe, declined."}
        )

    event = Events.objects.filter(id=event_id, deleted_at__isnull=True).first()
    if event is None:
        raise NotFound("Event not found.")

    if event.ends_datetime < timezone.now():
        raise ValidationError("Event has already ended; RSVP is closed.")

    if not can_user_rsvp_to_event(user, event):
        # 403 rather than 404 because the FE can already enumerate
        # the event via ``GET /events/v1/`` (which is currently
        # globally-visible). Hiding existence here would be theatre.
        raise PermissionDenied("You are not a target of this event.")

    rsvp, created = EventRsvp.objects.update_or_create(
        event=event,
        user=user,
        defaults={
            "rsvp_status": rsvp_status,
            "responded_at": timezone.now(),
        },
    )
    return event, rsvp, created


def register_user_for_event(user, event_id):
    """Backward-compatible alias for ``POST .../register/``.

    Equivalent to ``set_user_rsvp(user, event_id, GOING)``. Kept as a
    distinct function so the FE's existing ``register`` button doesn't
    need to know about the wider RSVP state machine; the gate logic
    is shared because both endpoints route through
    :func:`set_user_rsvp`.

    Returns ``(event, rsvp, created)`` matching the original signature.
    """
    return set_user_rsvp(user, event_id, EventRsvp.RsvpStatus.GOING)
