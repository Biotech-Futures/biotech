"""Business logic for the events app.

Permission model in one paragraph:

* Events are *pushed* — only admins create them. Global admins (is_staff
  / is_superuser / AdminScope.is_global) can CRUD any event. Track admins
  can CRUD only events whose track FK is in their AdminScope.
* Users RSVP. The user-side state machine is accepted / tentative /
  declined. PENDING is reserved for admin-issued invites awaiting a
  response and is rejected on the user-submit path.

`can_user_rsvp_to_event` is the single source of truth for "is this
user a target of this event?" Both the read queryset
(`visible_events_queryset`) and the write helper (`set_user_rsvp`)
funnel through the same rule so a user who can SEE an event can RSVP
to it, and vice-versa.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
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

logger = logging.getLogger(__name__)


def get_user_accepted_event_ids(user):
    """Return event ids the user has ACCEPTED.

    The set is the truth behind both `EventSerializer.accepted` and the
    `?accepted=true` filter, so the contract change happens here only.
    Tentative / declined / pending all serialize as `accepted: false`.
    """
    if not user or not user.is_authenticated:
        return set()
    return set(
        EventRsvp.objects.filter(
            user=user,
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
        ).values_list("event_id", flat=True)
    )


def get_request_accepted_event_ids(request):
    """Per-request memoized wrapper around `get_user_accepted_event_ids`.

    The list view's filter and serializer context both need this set;
    caching on `request` keeps it to one query per request.
    """
    if request is None:
        return set()
    cached = getattr(request, "_cached_accepted_event_ids", None)
    if cached is None:
        cached = get_user_accepted_event_ids(getattr(request, "user", None))
        request._cached_accepted_event_ids = cached
    return cached


# ---------------------------------------------------------------------------
# Visibility gate. Mirrored on the read side by visible_events_queryset.
# ---------------------------------------------------------------------------


def can_user_rsvp_to_event(user, event) -> bool:
    """True iff `user` may RSVP to `event`.

    Rules:
    * Global admin           → yes, always.
    * Track admin            → yes for events touching their tracks
                               (direct FK / EventTargetTrack / parent
                               track of any EventTargetGroup) or for
                               untargeted org-wide events.
    * Existing invitee       → yes, regardless of current status. A
                               declined user must be able to flip back.
    * Untargeted event       → yes for any authenticated user.
    * Targeted event         → user's scope must intersect every present
                               targeting axis (AND across axes, OR
                               within an axis). Same shape as the
                               dashboard's `_is_member_match`.
    """
    if not user or not user.is_authenticated:
        return False

    target_track_ids = _event_target_track_ids(event)
    target_group_ids = _event_target_group_ids(event)
    target_role_ids = _event_target_role_ids(event)
    is_untargeted = (
        not target_track_ids and not target_group_ids and not target_role_ids
    )

    if is_operational_admin(user):
        admin_track_ids = get_admin_track_ids(user)
        if admin_track_ids is None:
            return True
        if is_untargeted:
            return True
        admin_track_ids_set = set(admin_track_ids)
        # Tracks the event reaches — direct + via group's parent track.
        event_admin_relevant_tracks = set(target_track_ids) | {
            target.group.track_id
            for target in EventTargetGroup.objects.filter(event=event).select_related("group")
        }
        return bool(admin_track_ids_set & event_admin_relevant_tracks)

    # Pre-existing invite (any status, including DECLINED) keeps the
    # user in the loop.
    if EventRsvp.objects.filter(event=event, user=user).exists():
        return True

    if is_untargeted:
        return True

    user_group_ids, user_track_ids, user_role_ids = _user_scope(user)

    # AND across axes / OR within an axis.
    track_ok = (not target_track_ids) or bool(target_track_ids & user_track_ids)
    group_ok = (not target_group_ids) or bool(target_group_ids & user_group_ids)
    role_ok = (not target_role_ids) or bool(target_role_ids & user_role_ids)
    return track_ok and group_ok and role_ok


# ---------------------------------------------------------------------------
# Read-side scoping for GET /events/v1/. Mirrors the gate above.
# ---------------------------------------------------------------------------


def visible_events_queryset(user, base_qs):
    """Filter `base_qs` to events visible to `user`.

    * Anonymous              → untargeted only.
    * Global admin           → everything.
    * Track admin            → events touching their tracks ∪ untargeted.
    * Authenticated user     → invited ∪ untargeted ∪ targeting match
                               (AND across axes / OR within axis).

    Uses `Exists` subqueries so multi-axis filtering doesn't multiply
    rows (no DISTINCT needed).
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

    user_group_ids, user_track_ids, user_role_ids = _user_scope(user)
    invited_event_ids = EventRsvp.objects.filter(user=user).values("event_id")

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

    # Supervisor scope. A supervisor inherits read access to events that
    # target any of their supervisees' groups / tracks — they need to
    # see what's been pushed to their students.
    supervisor_q = _supervisor_visibility_q(user)

    return base_qs.filter(
        Q(id__in=invited_event_ids)
        | (track_axis_pass & group_axis_pass & role_axis_pass)
        | supervisor_q
    )


def _supervisor_visibility_q(user):
    """Q matching events visible through this user's supervisor scope.

    The supervisor sees events targeting any group their supervisees
    belong to, plus the parent tracks of those groups (direct FK or
    EventTargetTrack). Returns a never-matching Q if the user has no
    supervisees, so the caller can OR it in safely.
    """
    from apps.users.models import StudentProfile
    from apps.groups.models import GroupMembership

    supervisee_ids = list(
        StudentProfile.objects.filter(supervisor_id=user.id)
        .values_list("user_id", flat=True)
    )
    if not supervisee_ids:
        return Q(pk__in=[])

    rows = list(
        GroupMembership.objects.filter(
            user_id__in=supervisee_ids, left_at__isnull=True
        ).values_list("group_id", "group__track_id")
    )
    group_ids = sorted({r[0] for r in rows if r[0]})
    track_ids = sorted({r[1] for r in rows if r[1]})
    if not group_ids and not track_ids:
        return Q(pk__in=[])

    q = Q(pk__in=[])
    if track_ids:
        q = q | Q(track_id__in=track_ids) | Exists(
            EventTargetTrack.objects.filter(
                event_id=OuterRef("id"),
                track_id__in=track_ids,
            )
        )
    if group_ids:
        q = q | Exists(
            EventTargetGroup.objects.filter(
                event_id=OuterRef("id"),
                group_id__in=group_ids,
            )
        )
    return q


def _event_target_track_ids(event) -> set:
    """Direct event.track FK ∪ EventTargetTrack rows."""
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
    """(group_ids, track_ids, role_ids) for `user`.

    Tracks come from the user's group memberships' parent tracks plus
    `user.track_id` if that field exists on the User model.
    """
    # Imports kept local to dodge circular-import risk between events,
    # groups, and resources.
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
    user_role_ids = set(
        RoleAssignmentHistory.objects.filter(user=user, valid_from__lte=now)
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
        .values_list("role_id", flat=True)
    )
    return user_group_ids, user_track_ids, user_role_ids


# ---------------------------------------------------------------------------
# RSVP write path. Both /register/ and /rsvp/ funnel through here.
# ---------------------------------------------------------------------------

# PENDING is admin-only — it's the state an invite sits in until the
# user responds. Letting users submit it would silently overwrite
# admin invites.
USER_SUBMITTABLE_RSVP_STATUSES = (
    EventRsvp.RsvpStatus.ACCEPTED,
    EventRsvp.RsvpStatus.TENTATIVE,
    EventRsvp.RsvpStatus.DECLINED,
)


def set_user_rsvp(user, event_id, rsvp_status):
    """Upsert `user`'s RSVP on `event_id` to `rsvp_status`.

    Returns `(event, rsvp, created)`. Raises:
        NotFound          — event missing or soft-deleted.
        ValidationError   — event already ended, or status not user-submittable.
        PermissionDenied  — user is not a target of the event.
    """
    if rsvp_status not in USER_SUBMITTABLE_RSVP_STATUSES:
        raise ValidationError(
            {"rsvp_status": "Must be one of: accepted, tentative, declined."}
        )

    event = Events.objects.filter(id=event_id, deleted_at__isnull=True).first()
    if event is None:
        raise NotFound("Event not found.")

    if event.ends_datetime < timezone.now():
        raise ValidationError("Event has already ended; RSVP is closed.")

    if not can_user_rsvp_to_event(user, event):
        # 403 over 404: events are listable via GET, so hiding existence
        # here would be theatre.
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


# ---------------------------------------------------------------------------
# 24h RSVP reminder dispatch. Invoked by:
#   * `manage.py send_rsvp_reminders`
#   * the POST /events/v1/admin/send-rsvp-reminders/ endpoint (guarded by
#     RSVP_REMINDER_TOKEN), which the hourly GitHub Actions workflow hits.
#
# Why this lives in services.py rather than a Celery task:
# we don't want a broker/worker just for one cron job. An external
# scheduler triggers the same code path via the management command or
# the admin endpoint.
# ---------------------------------------------------------------------------


# Default window constants — callers can override by passing explicit
# hours to send_due_rsvp_reminders(). Keeping them here as defaults
# means the GitHub Actions trigger and management command require no
# changes for the standard case.
RSVP_REMINDER_24H_WINDOW_START = 24
RSVP_REMINDER_24H_WINDOW_END = 25
RSVP_REMINDER_1H_WINDOW_START = 1
RSVP_REMINDER_1H_WINDOW_END = 2

# How many RSVPs to pull from the DB per chunk inside one event. Keeps
# memory flat for events with very large attendee lists.
RSVP_REMINDER_RSVP_CHUNK_SIZE = 100


def send_due_rsvp_reminders(
    window_start_hours=None,
    window_end_hours=None,
):
    """Dispatch reminder emails for events within the given time window.

    Called twice per cycle:
      * 24h window — emails ACCEPTED attendees + nudges PENDING attendees
      * 1h window  — emails ACCEPTED attendees only (final reminder)

    ``window_start_hours`` and ``window_end_hours`` default to the 24h
    window constants so the existing management command and GitHub Actions
    trigger require no changes.

    Returns ``(events_processed, emails_sent, emails_failed)``.

    Idempotency: separate ``reminder_sent`` and ``reminder_1h_sent``
    boolean flags guard each window so a crash or parallel worker cannot
    send duplicate emails.
    """
    if window_start_hours is None:
        window_start_hours = RSVP_REMINDER_24H_WINDOW_START
    if window_end_hours is None:
        window_end_hours = RSVP_REMINDER_24H_WINDOW_END

    is_1h_window = window_start_hours < 2  # treat anything under 2h as the 1h pass

    now = timezone.now()
    window_start = now + timedelta(hours=window_start_hours)
    window_end = now + timedelta(hours=window_end_hours)

    # Select the correct idempotency flag for this window
    if is_1h_window:
        candidates = Events.objects.filter(
            start_datetime__gte=window_start,
            start_datetime__lt=window_end,
            deleted_at__isnull=True,
            reminder_1h_sent=False,
        )
    else:
        candidates = Events.objects.filter(
            start_datetime__gte=window_start,
            start_datetime__lt=window_end,
            deleted_at__isnull=True,
            reminder_sent=False,
        )

    events_processed = 0
    total_sent = 0
    total_failed = 0

    for event in candidates:
        # Atomic claim using the correct flag
        if is_1h_window:
            claimed = Events.objects.filter(
                pk=event.pk, reminder_1h_sent=False
            ).update(reminder_1h_sent=True)
        else:
            claimed = Events.objects.filter(
                pk=event.pk, reminder_sent=False
            ).update(reminder_sent=True)

        if not claimed:
            continue

        try:
            if is_1h_window:
                # 1h window — confirmed attendees only, final reminder
                sent, failed = _send_reminders_for_event(
                    event,
                    statuses=[EventRsvp.RsvpStatus.ACCEPTED],
                    subject_prefix="Starting soon",
                )
            else:
                # 24h window — confirmed attendees get full reminder,
                # pending attendees get a nudge to respond
                sent, failed = _send_reminders_for_event(
                    event,
                    statuses=[EventRsvp.RsvpStatus.ACCEPTED],
                    subject_prefix="Reminder",
                )
                nudge_sent, nudge_failed = _send_reminders_for_event(
                    event,
                    statuses=[EventRsvp.RsvpStatus.PENDING],
                    subject_prefix="Please respond",
                    is_nudge=True,
                )
                sent += nudge_sent
                failed += nudge_failed
        except Exception:
            logger.exception(
                "RSVP reminder dispatch crashed for event %s", event.id
            )
            continue

        events_processed += 1
        total_sent += sent
        total_failed += failed
        logger.info(
            "RSVP reminders for event %s (%s): sent=%s failed=%s window=%sh",
            event.id,
            event.event_name,
            sent,
            failed,
            window_start_hours,
        )

    return events_processed, total_sent, total_failed


def _send_reminders_for_event(event, statuses=None, subject_prefix="Reminder", is_nudge=False):
    """Email attendees of `event` whose RSVP status is in `statuses`.

    Returns ``(sent, failed)``.

    ``is_nudge=True`` swaps in the pending-nudge body so PENDING
    attendees get a different message asking them to respond rather
    than a confirmation reminder.
    """
    if statuses is None:
        statuses = [EventRsvp.RsvpStatus.ACCEPTED]

    rsvps = (
        EventRsvp.objects.filter(
            event=event,
            rsvp_status__in=statuses,
        )
        .select_related("user")
        .iterator(chunk_size=RSVP_REMINDER_RSVP_CHUNK_SIZE)
    )

    if is_nudge:
        body_template = _rsvp_nudge_body_template(event)
        subject = f"{subject_prefix}: {event.event_name} — have you responded?"
    else:
        body_template = _rsvp_reminder_body_template(event)
        subject = f"{subject_prefix}: {event.event_name}"

    from_email = settings.DEFAULT_FROM_EMAIL or "noreply@biotechfutures.com"

    sent = 0
    failed = 0
    for rsvp in rsvps:
        user = rsvp.user
        email = getattr(user, "email", None)
        if not email:
            continue
        first_name = (getattr(user, "first_name", "") or "").strip() or "there"
        try:
            send_mail(
                subject=subject,
                message=body_template.format(first_name=first_name),
                from_email=from_email,
                recipient_list=[email],
                fail_silently=False,
            )
            sent += 1
        except Exception:
            failed += 1
            logger.exception(
                "Failed to send RSVP reminder for event %s to user %s",
                event.id,
                user.id,
            )
    return sent, failed


def _rsvp_reminder_body_template(event):
    """Return a ``str.format``-ready body with a ``{first_name}`` slot.

    Built once per event so we don't re-render the location block for
    every recipient.
    """
    if event.is_virtual:
        if event.location_link:
            location_line = f"Join online: {event.location_link}"
        else:
            location_line = (
                "This is a virtual event. Check your calendar invite for the link."
            )
    else:
        # Non-virtual events can legitimately have a null `location`
        # (the model allows it) — fall back to the map link, then to
        # nothing, rather than emailing "Location: None".
        parts = []
        if event.location:
            parts.append(f"Location: {event.location}")
        if event.location_link:
            parts.append(f"Map: {event.location_link}")
        location_line = "\n".join(parts) if parts else ""

    when = event.start_datetime.strftime("%A, %d %B %Y at %I:%M %p")
    body = (
        "Hi {first_name},\n\n"
        "This is a friendly reminder that you have an upcoming event:\n\n"
        f"Event:  {event.event_name}\n"
        f"Date:   {when}\n"
    )
    if location_line:
        body += f"{location_line}\n"
    body += "\nWe look forward to seeing you there!\n\nThe BIOTech Futures Team"
    return body

def _rsvp_nudge_body_template(event):
    """Return a nudge body for PENDING attendees who haven't responded yet."""
    when = event.start_datetime.strftime("%A, %d %B %Y at %I:%M %p")
    body = (
        "Hi {first_name},\n\n"
        f"You have been invited to {event.event_name} happening tomorrow "
        f"on {when} but we haven't received your response yet.\n\n"
        "Please log in to confirm whether you will be attending.\n\n"
        "The BIOTech Futures Team"
    )
    return body