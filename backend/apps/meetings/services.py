"""Scheduling and persistence for mentor-run group meetings.

The schedule is stored on ``events.Events`` rather than duplicated here,
and that is the whole point of this module. Creating the Events row plus
one ``EventRsvp`` per group member is what puts the meeting in every
member's in-app calendar AND what arms the existing 24h / 1h reminder
dispatcher (``apps.events.services.send_due_rsvp_reminders``, driven by
the hourly .github/workflows/rsvp-reminders.yml cron). Neither behaviour
is reimplemented here.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from apps.events.models import EventRsvp, EventTargetGroup, Events
from apps.events.services import visible_events_queryset
from apps.groups.models import GroupMembership

from .models import GroupMeeting, MeetingNote, MeetingSummary

logger = logging.getLogger(__name__)


# Meetings are Events carrying this type. Any surface that wants "real"
# programme events (the admin console list) should exclude it.
MEETING_EVENT_TYPE = Events.EventTypeChoices.GROUP_MEETING


class StaleRevision(Exception):
    """The client's note revision no longer matches the stored row."""

    def __init__(self, current):
        self.current = current
        super().__init__(f"Note has moved on; current revision is {current}.")


def meeting_channel_name(meeting_id) -> str:
    """Channel-layer group name. Single source of truth for the consumer."""
    return f"meeting_{meeting_id}"


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


@transaction.atomic
def schedule_meeting(
    *,
    organiser,
    group,
    name,
    start,
    end,
    join_link,
    description="",
    agenda="",
    timezone_name="UTC",
):
    """Create a meeting and put it in every group member's calendar."""
    event = Events.objects.create(
        event_name=name,
        description=description or "",
        event_type=MEETING_EVENT_TYPE,
        start_datetime=start,
        ends_datetime=end,
        event_timezone=timezone_name or "UTC",
        # Virtual by definition -- the meeting IS the join link. `location`
        # must stay null: check_event_format_location_consistency rejects a
        # virtual event that also carries a physical address.
        event_format=Events.EventFormat.VIRTUAL,
        location=None,
        location_link=join_link,
        host_user=organiser,
    )

    # Scopes the event through apps.events.services.visible_events_queryset,
    # so a non-member gets a 404 on it from the events API too -- one
    # visibility rule, not two.
    EventTargetGroup.objects.create(event=event, group=group)

    meeting = GroupMeeting.objects.create(
        event=event,
        group=group,
        organiser=organiser,
        agenda=agenda or "",
    )
    MeetingNote.objects.create(meeting=meeting)
    sync_attendees(meeting)
    return meeting


def sync_attendees(meeting) -> int:
    """Create a PENDING RSVP for every active member that lacks one.

    This is the calendar hookup: the reminder dispatcher selects on RSVP
    rows and the FE calendar reads the events list. Existing rows are left
    untouched so re-running after a membership change never resets somebody's
    answer. The organiser is seeded ACCEPTED -- they called the meeting.

    Returns the number of rows added.
    """
    member_ids = set(
        GroupMembership.objects.filter(
            group_id=meeting.group_id,
            left_at__isnull=True,
        ).values_list("user_id", flat=True)
    )
    if meeting.organiser_id:
        member_ids.add(meeting.organiser_id)

    existing = set(
        EventRsvp.objects.filter(
            event_id=meeting.event_id, user_id__in=member_ids
        ).values_list("user_id", flat=True)
    )
    missing = sorted(member_ids - existing)
    if not missing:
        return 0

    now = timezone.now()
    EventRsvp.objects.bulk_create(
        [
            EventRsvp(
                event_id=meeting.event_id,
                user_id=uid,
                rsvp_status=(
                    EventRsvp.RsvpStatus.ACCEPTED
                    if uid == meeting.organiser_id
                    else EventRsvp.RsvpStatus.PENDING
                ),
                # The event_rsvp_response_state_valid CHECK allows a stamp
                # only on a non-PENDING row.
                responded_at=now if uid == meeting.organiser_id else None,
            )
            for uid in missing
        ],
        # A concurrent schedule + membership sync would otherwise trip
        # unique_event_rsvp_user.
        ignore_conflicts=True,
    )
    return len(missing)


@transaction.atomic
def update_meeting(meeting, **changes):
    """Apply a partial edit.

    Rescheduling re-arms the reminders for free: the 24h/1h idempotency
    stamps store the ``start_datetime`` they fired for, so writing a new
    start makes them stop matching and the dispatcher treats the meeting as
    un-reminded. Nothing to clear.
    """
    field_map = {
        "title": "event_name",
        "description": "description",
        "start_datetime": "start_datetime",
        "ends_datetime": "ends_datetime",
        "join_link": "location_link",
        "timezone_name": "event_timezone",
    }
    event = meeting.event
    event_fields = []
    for key, column in field_map.items():
        if key in changes:
            setattr(event, column, changes[key])
            event_fields.append(column)
    if event_fields:
        event.save(update_fields=event_fields)

    if "agenda" in changes:
        meeting.agenda = changes["agenda"] or ""
        meeting.save(update_fields=["agenda", "updated_at"])
    return meeting


def reschedule_meeting(meeting, *, start, end):
    """Convenience wrapper for the common case."""
    return update_meeting(meeting, start_datetime=start, ends_datetime=end)


def cancel_meeting(meeting):
    """Soft-delete.

    Drops the meeting out of the calendar and out of the reminder
    dispatcher's candidate query in a single write.
    """
    event = meeting.event
    if event.deleted_at is None:
        event.deleted_at = timezone.now()
        event.save(update_fields=["deleted_at"])
    return meeting


def visible_meetings_queryset(user, *, include_cancelled=False):
    """Meetings ``user`` may see, reusing the events visibility rules.

    Delegating to visible_events_queryset means supervisor inheritance and
    the admin override behave identically here and on the events API --
    one implementation instead of two that drift apart.
    """
    events = Events.objects.filter(event_type=MEETING_EVENT_TYPE)
    if not include_cancelled:
        events = events.filter(deleted_at__isnull=True)

    return GroupMeeting.objects.filter(
        event__in=visible_events_queryset(user, events)
    ).select_related("event", "group", "organiser")


# ---------------------------------------------------------------------------
# Shared live note
# ---------------------------------------------------------------------------


def get_or_create_note(meeting):
    note, _ = MeetingNote.objects.get_or_create(meeting=meeting)
    return note


@transaction.atomic
def update_note(meeting, *, user, body, revision=None):
    """Write the shared note under optimistic concurrency.

    ``revision`` is the value the client last read. Pass None to force a
    last-writer-wins write; pass the read revision to get StaleRevision
    (-> 409) instead of a silent clobber.
    """
    note = MeetingNote.objects.select_for_update().filter(meeting=meeting).first()
    if note is None:
        note = MeetingNote.objects.create(meeting=meeting)

    if revision is not None and revision != note.revision:
        raise StaleRevision(note.revision)

    note.body = body
    note.revision = note.revision + 1
    note.updated_by = user
    note.save(update_fields=["body", "revision", "updated_by", "updated_at"])
    return note


def broadcast_note(meeting, note):
    """Fan the new body out to everyone on the meeting's socket.

    Same split as apps.chat: REST persists, the socket is pure fan-out. A
    dead Redis must not fail the user's save -- the note is already
    committed and the next fetch will show it.
    """
    layer = get_channel_layer()
    if layer is None:
        return
    payload = {
        "event": "note.updated",
        "type": "note.updated",
        "meeting_id": meeting.id,
        "body": note.body,
        "revision": note.revision,
        "updated_by": note.updated_by_id,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }
    try:
        async_to_sync(layer.group_send)(
            meeting_channel_name(meeting.id),
            {"type": "meeting.event", "payload": payload},
        )
    except Exception:
        logger.exception("Failed to broadcast note update for meeting %s", meeting.id)


# ---------------------------------------------------------------------------
# Mentor summary
# ---------------------------------------------------------------------------


@transaction.atomic
def upsert_summary(meeting, *, author, body, publish=None):
    """Create or replace the mentor's summary.

    ``publish`` None leaves the draft/published state alone; True stamps
    published_at (first time only, so it records first publication); False
    reverts to draft.
    """
    summary, _ = MeetingSummary.objects.select_for_update().get_or_create(
        meeting=meeting,
        defaults={"author": author},
    )
    summary.body = body
    summary.author = author
    if publish is True and summary.published_at is None:
        summary.published_at = timezone.now()
    elif publish is False:
        summary.published_at = None
    summary.save(update_fields=["body", "author", "published_at", "updated_at"])
    return summary
