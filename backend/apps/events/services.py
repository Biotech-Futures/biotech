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
from django.core.mail import EmailMultiAlternatives
from django.db.models import Exists, OuterRef, Q
from django.template.loader import render_to_string
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


def send_due_event_rsvp_reminders(*, now=None, hours_ahead=None, window_hours=None, dry_run=False):
    """Send reminder emails for due events without requiring Celery.

    Developer note: Azure can invoke the management command on an hourly
    schedule. Keeping the core logic in a plain service makes it testable and
    avoids introducing a background-worker stack the repo does not otherwise use.
    """
    now = now or timezone.now()
    hours_ahead = (
        settings.EVENT_RSVP_REMINDER_HOURS_AHEAD
        if hours_ahead is None
        else int(hours_ahead)
    )
    window_hours = (
        settings.EVENT_RSVP_REMINDER_WINDOW_HOURS
        if window_hours is None
        else int(window_hours)
    )

    window_start = now + timedelta(hours=hours_ahead)
    window_end = window_start + timedelta(hours=window_hours)
    # the default 24h→25h window assumes the command runs
    # hourly. That gives each eligible event one capture window without needing
    # Celery beat or minute-level scheduling guarantees.
    due_events = [
        event
        for event in Events.objects.filter(
            start_datetime__gte=window_start,
            start_datetime__lt=window_end,
            deleted_at__isnull=True,
        ).order_by("start_datetime", "id")
        if event.rsvp_reminder_sent_for_start != event.start_datetime
    ]

    summary = {
        "events_considered": len(due_events),
        "events_marked": 0,
        "emails_sent": 0,
        "emails_failed": 0,
        "emails_skipped": 0,
        "dry_run": bool(dry_run),
    }

    for event in due_events:
        event_summary = _send_event_rsvp_reminders_for_event(
            event,
            dry_run=dry_run,
        )
        summary["events_marked"] += 1 if event_summary["event_marked"] else 0
        summary["emails_sent"] += event_summary["emails_sent"]
        summary["emails_failed"] += event_summary["emails_failed"]
        summary["emails_skipped"] += event_summary["emails_skipped"]
    return summary


def _send_event_rsvp_reminders_for_event(event, *, dry_run=False):
    accepted_rsvps = (
        EventRsvp.objects.filter(
            event=event,
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
        )
        .select_related("user")
        .order_by("id")
    )

    sent = 0
    failed = 0
    skipped = 0
    for rsvp in accepted_rsvps.iterator(chunk_size=100):
        user = rsvp.user
        recipient = getattr(user, "email", "") or ""
        if not recipient.strip():
            skipped += 1
            continue

        if dry_run:
            sent += 1
            continue

        try:
            _send_event_rsvp_reminder_email(user, event)
            sent += 1
        except Exception:
            failed += 1
            logger.exception(
                "event_rsvp_reminder.send_failed",
                extra={"event_id": event.id, "user_id": user.id},
            )

    event_marked = False
    if not dry_run:
        # mark the event after the pass even if some emails
        # failed. That avoids duplicate sends to recipients who already got the
        # reminder; operators can retry failed addresses manually from logs.
        Events.objects.filter(pk=event.pk).update(
            rsvp_reminder_sent_for_start=event.start_datetime
        )
        event_marked = True

    logger.info(
        "event_rsvp_reminder.completed",
        extra={
            "event_id": event.id,
            "sent": sent,
            "failed": failed,
            "skipped": skipped,
            "dry_run": dry_run,
        },
    )
    return {
        "event_marked": event_marked,
        "emails_sent": sent,
        "emails_failed": failed,
        "emails_skipped": skipped,
    }


def _send_event_rsvp_reminder_email(user, event):
    start_local = timezone.localtime(event.start_datetime)
    ctx = {
        "First_Name": user.first_name or "there",
        "EVENT_NAME": event.event_name,
        "EVENT_DATE": start_local.strftime("%A, %d %B %Y"),
        "EVENT_TIME": start_local.strftime("%I:%M %p %Z").strip(),
        "EVENT_LOCATION": _event_location_label(event),
        "EVENT_DESCRIPTION": event.description or "",
        "CONTACT_EMAIL": settings.DEFAULT_FROM_EMAIL,
    }

    html_content = render_to_string("emails/event_rsvp_reminder.html", ctx)
    text_content = (
        f"Hi {ctx['First_Name']},\n\n"
        f"This is a reminder that {ctx['EVENT_NAME']} starts in about 24 hours.\n"
        f"Date: {ctx['EVENT_DATE']}\n"
        f"Time: {ctx['EVENT_TIME']}\n"
        f"Location: {ctx['EVENT_LOCATION']}\n"
    )
    if ctx["EVENT_DESCRIPTION"]:
        text_content += f"Details: {ctx['EVENT_DESCRIPTION']}\n"
    text_content += "\nWe look forward to seeing you there.\n\nThe BIOTech Futures Team"

    msg = EmailMultiAlternatives(
        subject=f"Reminder: {event.event_name} starts tomorrow",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()


def _event_location_label(event):
    if getattr(event, "is_virtual", False):
        if event.location_link:
            return f"Virtual event: {event.location_link}"
        return "Virtual event"

    if event.location and event.location_link:
        return f"{event.location} ({event.location_link})"
    return event.location or "Location to be confirmed"
