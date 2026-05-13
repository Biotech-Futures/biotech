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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Exists, F, OuterRef, Q
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


# ---------------------------------------------------------------------------
# RSVP reminder dispatch. Triggered hourly by the Azure WebJob
# (deployment/azure/webjobs/rsvp-reminders/) and by the HMAC-guarded
# POST /events/v1/admin/send-rsvp-reminders/ endpoint as an ops escape
# hatch — both call send_due_rsvp_reminders().
# ---------------------------------------------------------------------------


REMINDER_RSVP_CHUNK_SIZE = 100


# A "kind" is one (window, idempotency field) pair. Multiple audiences
# can fire under a single atomic claim per kind.
REMINDER_KINDS = {
    "24h": {
        "field": "reminder_24h_sent_for_start",
        "hours_ahead_setting": "RSVP_REMINDER_24H_HOURS_AHEAD",
        "window_hours_setting": "RSVP_REMINDER_24H_WINDOW_HOURS",
        "audiences": (
            {
                "statuses": (EventRsvp.RsvpStatus.ACCEPTED,),
                "subject": "Reminder: {event_name}",
                "headline": "Your event is tomorrow",
                "intro": (
                    "This is a friendly reminder that you have an upcoming "
                    "event with BIOTech Futures tomorrow."
                ),
                "closing": "We look forward to seeing you there!",
                "preheader_phrase": "starts in about 24 hours",
            },
            {
                "statuses": (EventRsvp.RsvpStatus.PENDING,),
                "subject": "Please respond: {event_name}",
                "headline": "Please respond",
                "intro": (
                    "You have been invited to this event tomorrow, but we "
                    "haven't received your response yet. Please log in to "
                    "let us know whether you'll be attending."
                ),
                "closing": "Thanks for letting us know.",
                "preheader_phrase": "is tomorrow — please respond",
            },
        ),
    },
    "1h": {
        "field": "reminder_1h_sent_for_start",
        "hours_ahead_setting": "RSVP_REMINDER_1H_HOURS_AHEAD",
        "window_hours_setting": "RSVP_REMINDER_1H_WINDOW_HOURS",
        "audiences": (
            {
                "statuses": (EventRsvp.RsvpStatus.ACCEPTED,),
                "subject": "Starting soon: {event_name}",
                "headline": "Starting soon",
                "intro": (
                    "Just a quick reminder — your BIOTech Futures event "
                    "starts in about an hour."
                ),
                "closing": "See you very soon!",
                "preheader_phrase": "starts in about an hour",
            },
        ),
    },
}


def send_due_rsvp_reminders(*, kind=None, dry_run=False):
    """Dispatch RSVP reminder emails for events in their reminder windows.

    kind=None scans every configured kind; pass "24h" or "1h" to scan
    one. dry_run=True reports counts without claiming or sending.
    Returns (events_processed, emails_sent, emails_failed) summed
    across kinds.
    """
    if kind is None:
        kinds = tuple(REMINDER_KINDS.keys())
    elif kind in REMINDER_KINDS:
        kinds = (kind,)
    else:
        raise ValueError(
            f"Unknown reminder kind {kind!r}; choose from {sorted(REMINDER_KINDS)}."
        )

    events_processed = 0
    emails_sent = 0
    emails_failed = 0
    for k in kinds:
        ev, sent, failed = _dispatch_reminder_kind(k, dry_run=dry_run)
        events_processed += ev
        emails_sent += sent
        emails_failed += failed
    return events_processed, emails_sent, emails_failed


def _dispatch_reminder_kind(kind, *, dry_run):
    cfg = REMINDER_KINDS[kind]
    field = cfg["field"]
    hours_ahead = int(getattr(settings, cfg["hours_ahead_setting"]))
    window_hours = int(getattr(settings, cfg["window_hours_setting"]))

    now = timezone.now()
    window_start = now + timedelta(hours=hours_ahead)
    window_end = now + timedelta(hours=hours_ahead + window_hours)

    candidates = (
        Events.objects.filter(
            start_datetime__gte=window_start,
            start_datetime__lt=window_end,
            deleted_at__isnull=True,
        )
        .exclude(**{field: F("start_datetime")})
        .order_by("start_datetime", "id")
    )

    events_processed = 0
    emails_sent = 0
    emails_failed = 0

    for event in candidates:
        if dry_run:
            # Best-effort: doesn't account for blank user emails skipped at send time.
            for audience in cfg["audiences"]:
                emails_sent += EventRsvp.objects.filter(
                    event=event, rsvp_status__in=audience["statuses"]
                ).count()
            events_processed += 1
            continue

        # Atomic claim — wins exactly once under concurrent runs.
        claimed = (
            Events.objects.filter(pk=event.pk)
            .exclude(**{field: F("start_datetime")})
            .update(**{field: event.start_datetime})
        )
        if not claimed:
            continue

        try:
            ev_sent, ev_failed = _send_reminders_for_event(event, cfg["audiences"])
        except Exception:
            logger.exception(
                "RSVP reminder dispatch crashed for event %s (kind=%s)",
                event.id,
                kind,
            )
            continue

        events_processed += 1
        emails_sent += ev_sent
        emails_failed += ev_failed
        logger.info(
            "RSVP reminders kind=%s event=%s (%s): sent=%s failed=%s",
            kind,
            event.id,
            event.event_name,
            ev_sent,
            ev_failed,
        )

    return events_processed, emails_sent, emails_failed


def _send_reminders_for_event(event, audiences):
    sent = 0
    failed = 0
    for audience in audiences:
        s, f = _send_audience_reminders(event, audience)
        sent += s
        failed += f
    return sent, failed


def _format_event_times_for_user(event, user_tz_name: str):
    # Recipient timezones can be any IANA name. An empty or invalid value
    # falls back to UTC so a bad DB row never blocks a reminder send.
    try:
        tz = ZoneInfo(user_tz_name or "UTC")
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    local = event.start_datetime.astimezone(tz)
    tz_label = local.tzname() or (user_tz_name or "UTC")
    when_full = local.strftime(f"%A, %d %B %Y at %I:%M %p {tz_label}")
    date_label = local.strftime("%A, %d %B %Y")
    time_label = local.strftime(f"%I:%M %p {tz_label}")
    return when_full, date_label, time_label


def _send_audience_reminders(event, audience):
    rsvps = (
        EventRsvp.objects.filter(
            event=event,
            rsvp_status__in=audience["statuses"],
        )
        .select_related("user")
        .iterator(chunk_size=REMINDER_RSVP_CHUNK_SIZE)
    )

    subject = audience["subject"].format(event_name=event.event_name)
    location_text, location_map_url = _event_location_lines(event)

    from_email = settings.DEFAULT_FROM_EMAIL or "noreply@biotechfutures.com"

    sent = 0
    failed = 0
    for rsvp in rsvps:
        user = rsvp.user
        email = (getattr(user, "email", "") or "").strip()
        if not email:
            continue
        first_name = (getattr(user, "first_name", "") or "").strip() or "there"
        when_full, date_label, time_label = _format_event_times_for_user(
            event, getattr(user, "timezone", "UTC")
        )

        ctx = {
            "First_Name": first_name,
            "HEADLINE": audience["headline"],
            "INTRO": audience["intro"],
            "CLOSING": audience["closing"],
            "PREHEADER": f"{event.event_name} {audience['preheader_phrase']}.",
            "EVENT_NAME": event.event_name,
            "EVENT_WHEN_TEXT": when_full,
            "EVENT_DATE": date_label,
            "EVENT_TIME": time_label,
            "EVENT_LOCATION_TEXT": location_text,
            "EVENT_LOCATION_MAP_URL": location_map_url,
            "EVENT_DESCRIPTION": event.description or "",
            "CONTACT_EMAIL": from_email,
        }

        try:
            _send_one_reminder(
                subject=subject,
                recipient=email,
                from_email=from_email,
                ctx=ctx,
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


def _send_one_reminder(*, subject, recipient, from_email, ctx):
    # Extracted so resilience tests can patch a single seam.
    plain_body = _build_plain_reminder_body(ctx)
    html_body = render_to_string("emails/rsvp_reminder.html", ctx)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=from_email,
        to=[recipient],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def _build_plain_reminder_body(ctx):
    lines = [
        f"Hi {ctx['First_Name']},",
        "",
        ctx["INTRO"],
        "",
        f"Event:  {ctx['EVENT_NAME']}",
        f"Date:   {ctx['EVENT_WHEN_TEXT']}",
    ]
    if ctx["EVENT_LOCATION_TEXT"]:
        lines.append(f"Location: {ctx['EVENT_LOCATION_TEXT']}")
    if ctx["EVENT_LOCATION_MAP_URL"]:
        lines.append(f"Map: {ctx['EVENT_LOCATION_MAP_URL']}")
    if ctx["EVENT_DESCRIPTION"]:
        lines += ["", f"Details: {ctx['EVENT_DESCRIPTION']}"]
    lines += ["", ctx["CLOSING"], "", "The BIOTech Futures Team"]
    return "\n".join(lines)


def _event_location_lines(event):
    # Virtual events flatten the join URL into the text line; in-person
    # splits into (location, map). Empty pair ⇒ omit the row entirely.
    if event.is_virtual:
        if event.location_link:
            return (f"Join online: {event.location_link}", "")
        return (
            "This is a virtual event. Check your calendar invite for the link.",
            "",
        )
    return (event.location or "", event.location_link or "")