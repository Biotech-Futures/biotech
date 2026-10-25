"""Replay every ticket's timeline again, now that a pause is not a stop.

``0007`` reconstructed ``awaiting_support_since`` for rows that predate the
column, using the rule ``services/lifecycle`` had at the time. That rule could
not tell two situations apart, because the column it was writing had no way to
hold the difference:

  * STOPPED — support answered, so nobody is waiting on us;
  * PAUSED  — a real wait was running and an agent parked the ticket.

``0008`` adds ``awaiting_support_paused``, which holds exactly that
difference, and lifecycle.set_status now reads it instead of guessing. Leave
``0007``'s replay alone and the two implementations of the same rule disagree,
which the invariant test in tests/apps/tickets/test_migrations.py measures
directly: 2 of 91 generated histories, both of them "reply and move to pending
user, then drag the ticket back". ``0007`` arms those at the drag; the service
now leaves them stopped, because support had already answered.

That disagreement is not only a test failing. A deployment that ran ``0007``
and stopped there would badge exactly those tickets red on the queue the
moment it came up, with the requester having said nothing — the defect this
fix removes from the service, arriving through the backfill instead.

So this is ``0007``'s replay with one distinction added, writing both columns:

    ticket created                          arm at created_at
    user_message                            arm if idle; no pause outstanding
    support_reply                           STOP   (anchor null, not paused)
    audit "status"   -> pending_user        PAUSE  (paused iff it was running)
    audit "resolve"                         PAUSE
    audit "status"   off-clock -> on-clock  RESUME (or stay stopped)
    audit "reopen"                          arm at the reopen

A new file rather than an edit to ``0007``: ``0007`` has already run on
developer databases and Django will not run it twice, and it could not have
written this column in any case, because ``0008`` is what creates it.

Claiming, assigning, internal notes, priority and category changes stay absent
from the event list on purpose — none of them is an answer, so none may move
the clock.

Idempotent: the replay starts from ``created_at`` and never reads the columns
it writes, so running it twice produces the same rows. Everything ``0007``'s
docstring says about batching, row locks and the empty production table holds
here unchanged.

Not reversible, for the same reason ``0007`` is not.
"""

from django.db import migrations

OFF_THE_CLOCK = ("pending_user", "resolved")
BATCH = 500

# Ordering within one instant, extending 0007's. A single lifecycle call
# writes its message and its audit row microseconds apart, but seeded data and
# any future bulk import can land them on the same timestamp. Anything that
# takes the clock off sorts after anything that puts it on, so a tie resolves
# the way the service does: add_support_reply(move_to_pending=True) writes a
# reply and a status change together, and the reply is what decides — it
# leaves the ticket STOPPED, never paused.
_TIE_ORDER = {"arm": 0, "arm_if_idle": 1, "resume": 2, "pause": 3, "stop": 4}


def backfill(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    TicketMessage = apps.get_model("tickets", "TicketMessage")
    AuditLog = apps.get_model("audit", "AuditLog")

    ids = list(Ticket.objects.values_list("pk", flat=True))
    for start in range(0, len(ids), BATCH):
        chunk = ids[start:start + BATCH]
        events = _events_for(chunk, TicketMessage, AuditLog)
        rows = list(Ticket.objects.filter(pk__in=chunk))
        for ticket in rows:
            anchor, paused = _replay(ticket, events.get(ticket.pk, []))
            ticket.awaiting_support_since = anchor
            ticket.awaiting_support_paused = paused
        Ticket.objects.bulk_update(
            rows, ["awaiting_support_since", "awaiting_support_paused"]
        )


def _events_for(ticket_ids, TicketMessage, AuditLog):
    """Two queries for the whole batch, grouped by ticket."""
    by_ticket = {}

    messages = TicketMessage.objects.filter(
        ticket_id__in=ticket_ids,
        deleted_at__isnull=True,
        message_type__in=("user_message", "support_reply"),
    ).values_list("ticket_id", "created_at", "message_type")
    for ticket_id, when, kind in messages:
        action = "arm_if_idle" if kind == "user_message" else "stop"
        by_ticket.setdefault(ticket_id, []).append((when, action))

    audit = AuditLog.objects.filter(
        entity_type="ticket",
        entity_id__in=ticket_ids,
        action__in=("status", "resolve", "reopen"),
    ).values_list("entity_id", "created_at", "action", "before_state", "after_state")
    for ticket_id, when, action, before, after in audit:
        resolved = _audit_action(action, before or {}, after or {})
        if resolved:
            by_ticket.setdefault(ticket_id, []).append((when, resolved))

    return by_ticket


def _audit_action(action, before, after):
    if action == "resolve":
        return "pause"
    if action == "reopen":
        return "arm"
    # action == "status"
    if after.get("status") in OFF_THE_CLOCK:
        return "pause"
    if before.get("status") in OFF_THE_CLOCK:
        return "resume"
    # open <-> in progress. Whose move it is did not change, so neither does
    # the clock.
    return None


def _replay(ticket, events):
    # Every ticket is with support the moment it exists.
    anchor = ticket.created_at
    paused = False
    for when, action in sorted(events, key=lambda e: (e[0], _TIE_ORDER[e[1]])):
        if action == "stop":
            anchor, paused = None, False
        elif action == "pause":
            anchor, paused = None, paused or anchor is not None
        elif action == "arm":
            anchor, paused = when, False
        elif action == "resume":
            # A screening ticket has no requester, so "stopped, waiting on
            # them" names nobody and an agent moving it back is the only door
            # out. lifecycle._resume_clock makes the same carve-out.
            if paused or ticket.created_by_id is None:
                anchor = when
            paused = False
        else:  # arm_if_idle
            if anchor is None:
                anchor = when
            paused = False

    # The current status is authoritative. It costs nothing and it means a gap
    # in the audit log can never leave a "pending user" or "resolved" ticket
    # showing on the queue's red card.
    if ticket.status in OFF_THE_CLOCK:
        return None, paused
    # A ticket that is not off the clock is not parked, whatever a hole in the
    # audit log implies, and a pause left standing here would be read the next
    # time it went off and came back.
    return anchor, False


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0008_ticket_awaiting_support_paused"),
        # AuditLog is read above, so its table has to exist by the time this
        # runs.
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
