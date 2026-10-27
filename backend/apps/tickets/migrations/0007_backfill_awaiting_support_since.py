"""Give every existing ticket the clock the new Overdue rule reads.

``0006`` adds ``awaiting_support_since`` as null. Null means "nobody is
waiting on support", so without this step every ticket in the database would
read as never overdue and the queue's red card would show zero on a backlog.

The value has to be the one ``services/lifecycle`` would have produced had the
column always existed. Two earlier attempts got that wrong by trying to infer
it, and both were caught by review rather than by a test:

* The first took the newest requester message. The live rule KEEPS a running
  anchor rather than restarting it, so on a ticket raised three days ago and
  chased one day ago the two differed by 48 hours — one side of a Normal
  ticket's 24-hour window.
* The second took the earliest unanswered requester message. Better, but it
  still only read messages, and **a status change is not a message**. An agent
  who uses "reply and move to pending user" and later drags the ticket back to
  Open leaves a timeline whose last entry is a support reply, so that version
  returned null while the live rule had the clock running from the drag-back.
  The ticket could never go red — the exact defect the client rejected,
  arriving through the backfill instead of through the service.

So this does not infer. It **replays**: every event the lifecycle service acts
on is recovered, put in order, and the same rules applied.

    ticket created                          arm at created_at
    user_message                            arm if not already running
    support_reply                           disarm
    audit "status"   -> pending_user        disarm
    audit "status"   off-clock -> on-clock  arm if not already running
    audit "resolve"                         disarm
    audit "reopen"                          arm

Claiming, assigning, internal notes, priority and category changes are absent
from that list on purpose: none of them is an answer, so none of them may move
the clock. That mirrors lifecycle exactly, and the invariant test in
tests/apps/tickets/test_migrations.py compares the two directly across every
history it can build rather than against example values.

The audit log is the source for state changes because it is structured:
``before_state``/``after_state`` are JSON, while the SYSTEM timeline message
for the same event is human copy ("Status changed to Open.") that would have
to be string-matched. A ticket whose audit rows are missing simply replays
fewer events, and the final guard below keeps the result honest either way:
the current status is authoritative, so a ticket sitting in an off-clock state
ends with a null anchor whatever the history said.

Two queries per batch rather than per ticket. Production has no tickets at all
— the app is absent from ``main`` and from every remote branch — and a
developer database holds a few dozen, but a backfill issuing two queries per
row would be a trap for anyone who runs this on a real table later.

Not reversible. Going back would mean deciding which nulls were "we never
knew" and which were "not with support", and the column did not exist before,
so there is nothing to restore.

No row locks, and that is a decision rather than an oversight. Between reading
a batch and writing it back there is a window in which a support reply that
stops a ticket's clock would be written over. Measured on a table of 770
tickets: 93ms for the whole run, of which the one full batch of 500 took
62.7ms and the remaining 270 rows took 29.3ms. Reaching the window needs the
new code already serving traffic while this migration has not run yet, which
is only possible inside one deploy, between 0006 and 0007. Production has no
tickets at that point, and the batch loop does not run at all on an empty
table. A ticket caught in the window has one column set back to what it was a
moment earlier; the next reply, move to pending or resolution on that ticket
puts it right. Taking the lock would mean holding every row of the table for
the length of the migration, which is a worse trade for anyone who does run
this against a real backlog later.
"""

from django.db import migrations

OFF_THE_CLOCK = ("pending_user", "resolved")
BATCH = 500

# Ordering within one instant. A single lifecycle call writes its message and
# its audit row microseconds apart, but seeded data and any future bulk import
# can land them on the same timestamp, and "arm" then "disarm" is not the same
# as "disarm" then "arm". Disarming sorts last so a tie resolves the way the
# service does: add_support_reply(move_to_pending=True) writes a reply and a
# status change together, and both of those stop the clock.
_TIE_ORDER = {"arm": 0, "arm_if_idle": 1, "disarm": 2}


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
            ticket.awaiting_support_since = _replay(ticket, events.get(ticket.pk, []))
        Ticket.objects.bulk_update(rows, ["awaiting_support_since"])


def _events_for(ticket_ids, TicketMessage, AuditLog):
    """Two queries for the whole batch, grouped by ticket."""
    by_ticket = {}

    messages = TicketMessage.objects.filter(
        ticket_id__in=ticket_ids,
        deleted_at__isnull=True,
        message_type__in=("user_message", "support_reply"),
    ).values_list("ticket_id", "created_at", "message_type")
    for ticket_id, when, kind in messages:
        action = "arm_if_idle" if kind == "user_message" else "disarm"
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
        return "disarm"
    if action == "reopen":
        return "arm"
    # action == "status"
    if after.get("status") in OFF_THE_CLOCK:
        return "disarm"
    if before.get("status") in OFF_THE_CLOCK:
        return "arm_if_idle"
    # open <-> in progress. Whose move it is did not change, so neither does
    # the clock.
    return None


def _replay(ticket, events):
    # Every ticket is with support the moment it exists.
    anchor = ticket.created_at
    for when, action in sorted(events, key=lambda e: (e[0], _TIE_ORDER[e[1]])):
        if action == "disarm":
            anchor = None
        elif action == "arm":
            anchor = when
        elif anchor is None:  # arm_if_idle
            anchor = when

    # The current status is authoritative. It costs nothing and it means a gap
    # in the audit log can never leave a "pending user" or "resolved" ticket
    # showing on the queue's red card.
    if ticket.status in OFF_THE_CLOCK:
        return None
    return anchor


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0006_ticket_awaiting_support_since"),
        # AuditLog is read above, so its table has to exist by the time this
        # runs.
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
