"""Every state change a ticket can undergo.

Views never assign ``ticket.status`` directly. The reason is that no state
change is only a state change — each one owes some combination of a timeline
message, an audit row, an email and a timestamp, and the combinations are not
guessable. Keeping them here is what makes "did we remember the audit row?"
answerable by reading one file.

Transition numbers (T1-T8) refer to the table in
.capstone/design/ticketing/03-state-machine.md §2.
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.audit.services import log_audit_event

from ..models import (
    Ticket,
    TicketAttachment,
    TicketChannel,
    TicketMessage,
    TicketMessageType,
    TicketStatus,
)
from . import emails, system_messages
from .numbering import allocate_ticket_number

AUDIT_ENTITY_TYPE = "ticket"


def _iso(value):
    """Audit payloads are plain JSON; datetimes have to go in as strings."""
    return value.isoformat() if value else None


def _region_snapshot(user) -> str:
    """The requester's country, frozen at submission time (DEC-006).

    A snapshot rather than a join, so the queue keeps filtering correctly
    after someone edits their profile or their account is deleted. No country
    on file means the empty string, which is the Unknown bucket.
    """
    return getattr(getattr(user, "country", None), "country_name", "") or ""


def _touch(ticket, *, user_visible: bool, **extra):
    """Move the ticket's clocks, plus whatever else changed, in one write.

    ``user_visible`` decides whether the requester's clock moves too. It is
    False for everything the requester cannot see: internal notes, hand-offs
    between agents, priority changes. Moving their clock for an invisible
    event floats the ticket to the top of their list with nothing new on the
    timeline, which tells them something is going on behind the scenes.

    This must be the last write to the ticket row in its transaction. Do not
    call ``ticket.save()`` afterwards: the timestamps are ``default=now``
    rather than ``auto_now``, so a later save would quietly write the stale
    in-memory values back over these.
    """
    now = timezone.now()
    fields = {"support_updated_at": now, **extra}
    if user_visible:
        fields["updated_at"] = now
    Ticket.objects.filter(pk=ticket.pk).update(**fields)
    # Keep the caller's copy honest without a second query.
    for name, value in fields.items():
        setattr(ticket, name, value)


def _add_message(ticket, *, message_type, body, author=None, attachments=None):
    """Append one row to the timeline, with any already-stored files on it.

    ``attachments`` carries metadata for blobs that are **already** in
    storage. Uploading has to finish before the transaction opens — holding a
    database transaction open across a network round-trip to Azure means one
    slow upload parks a row lock.
    """
    message = TicketMessage.objects.create(
        ticket=ticket,
        author=author,
        message_type=message_type,
        body=body,
    )
    for meta in attachments or ():
        TicketAttachment.objects.create(message=message, **meta)
    return message


# --------------------------------------------------------------------------
# T1 / T2 — a ticket comes into existence
# --------------------------------------------------------------------------

def create_ticket(*, user, category, subject, body, attachments=None) -> Ticket:
    """T1: someone submits the portal form.

    The number is allocated inside this transaction on purpose. If the insert
    fails the number goes back, rather than leaving a hole in the sequence
    that reads like a deleted ticket.
    """
    with transaction.atomic():
        ticket = Ticket.objects.create(
            ticket_number=allocate_ticket_number(),
            subject=subject,
            body=body,
            category=category,
            region=_region_snapshot(user),
            channel=TicketChannel.PORTAL,
            created_by=user,
        )
        _add_message(
            ticket,
            message_type=TicketMessageType.USER_MESSAGE,
            body=body,
            author=user,
            attachments=attachments,
        )
        _add_message(
            ticket,
            message_type=TicketMessageType.SYSTEM,
            body=system_messages.auto_acknowledgement(getattr(user, "first_name", "")),
        )
        # After commit, never inside the transaction: if this rolled back
        # with the email already sent, the requester would be holding a
        # receipt for a ticket that does not exist.
        transaction.on_commit(lambda: emails.send_ticket_submitted(ticket))
    return ticket


# --------------------------------------------------------------------------
# T5 / T7 — the requester says something
# --------------------------------------------------------------------------

def add_user_reply(*, ticket, user, body, attachments=None) -> TicketMessage:
    """The requester replies. What that means depends on where the ticket is.

    On a resolved ticket it reopens it (T7). On one that was waiting for them
    it hands the ball back to support (T5). Otherwise it is just a message.
    """
    if ticket.created_by_id != getattr(user, "id", None):
        raise PermissionDenied("Only the requester can reply to this ticket.")

    with transaction.atomic():
        message = _add_message(
            ticket,
            message_type=TicketMessageType.USER_MESSAGE,
            body=body,
            author=user,
            attachments=attachments,
        )
        if ticket.status == TicketStatus.RESOLVED:
            reopen(ticket=ticket, actor=user)
        elif ticket.status == TicketStatus.PENDING_USER:
            _add_message(
                ticket,
                message_type=TicketMessageType.SYSTEM,
                body=system_messages.status_changed(TicketStatus.IN_PROGRESS),
            )
            # No audit row: this is the requester acting, not an agent.
            _touch(ticket, user_visible=True, status=TicketStatus.IN_PROGRESS)
        else:
            _touch(ticket, user_visible=True)
    return message


def reopen(*, ticket, actor) -> None:
    """T7: a reply on a resolved ticket puts it back in the open pool.

    The owner is cleared deliberately (DEC-008) — whoever resolved it may be
    off shift, and a reopened ticket sitting under their name is a ticket
    nobody is looking at.
    """
    before_state = {
        "status": ticket.status,
        "assignee_id": ticket.assignee_id,
        "resolved_at": _iso(ticket.resolved_at),
    }
    with transaction.atomic():
        _add_message(
            ticket,
            message_type=TicketMessageType.SYSTEM,
            body=system_messages.REOPENED,
        )
        log_audit_event(
            # The requester triggered this, not an agent.
            actor=actor,
            entity_type=AUDIT_ENTITY_TYPE,
            entity_id=ticket.pk,
            action="reopen",
            before_state=before_state,
            after_state={"status": TicketStatus.OPEN, "assignee_id": None, "resolved_at": None},
        )
        _touch(
            ticket,
            user_visible=True,
            status=TicketStatus.OPEN,
            assignee=None,
            resolved_at=None,
        )


# --------------------------------------------------------------------------
# Support-side messages
# --------------------------------------------------------------------------

def add_support_reply(*, ticket, actor, body, attachments=None) -> TicketMessage:
    """An agent answers the requester.

    Also the only place ``first_response_at`` is set, and it is set with a
    conditional update rather than a read-then-write: two agents replying at
    the same moment would otherwise both see it empty and both write.
    """
    with transaction.atomic():
        message = _add_message(
            ticket,
            message_type=TicketMessageType.SUPPORT_REPLY,
            body=body,
            author=actor,
            attachments=attachments,
        )
        now = timezone.now()
        stamped = Ticket.objects.filter(
            pk=ticket.pk, first_response_at__isnull=True
        ).update(first_response_at=now)
        if stamped:
            ticket.first_response_at = now
        _touch(ticket, user_visible=True)
        # Sent from this one place, not from mark_pending() as well, or
        # "reply and move to pending" would send two emails for one action.
        transaction.on_commit(lambda: emails.send_ticket_reply(ticket))
    return message


def add_internal_note(*, ticket, actor, body, attachments=None) -> TicketMessage:
    """A note between agents. The requester must never learn it happened.

    Hence no email, no audit row, and only the support-side clock moves.
    """
    with transaction.atomic():
        message = _add_message(
            ticket,
            message_type=TicketMessageType.INTERNAL_NOTE,
            body=body,
            author=actor,
            attachments=attachments,
        )
        _touch(ticket, user_visible=False)
    return message


# --------------------------------------------------------------------------
# T3 / hand-off — who owns the ticket
# --------------------------------------------------------------------------

def _assign_one(ticket, *, actor, assignee) -> None:
    """Give a ticket an owner.

    Two different things wear the same UI control:

    Picking up an unowned ticket is T3 — it starts the work, so the status
    moves and the requester is told ("your ticket is now being handled").

    Passing an already-owned ticket to a colleague is a hand-off. Nothing
    about it is the requester's business, so no message is written and their
    clock does not move (DEC-017, and D1 in decisions.md:417). The support
    side reads hand-off history from the audit log instead.
    """
    before_state = {"assignee_id": ticket.assignee_id}
    after_state = {"assignee_id": getattr(assignee, "pk", None)}
    picked_up_from_the_pool = ticket.status == TicketStatus.OPEN

    with transaction.atomic():
        if picked_up_from_the_pool:
            _add_message(
                ticket,
                message_type=TicketMessageType.SYSTEM,
                # Says what changed, never who took it. Naming the agent to
                # the requester is what DEC-017 rules out.
                body=system_messages.TICKET_NOW_HANDLED,
            )
        log_audit_event(
            actor=actor,
            entity_type=AUDIT_ENTITY_TYPE,
            entity_id=ticket.pk,
            action="assign",
            before_state=before_state,
            after_state=after_state,
        )
        if picked_up_from_the_pool:
            _touch(
                ticket,
                user_visible=True,
                assignee=assignee,
                status=TicketStatus.IN_PROGRESS,
            )
        else:
            _touch(ticket, user_visible=False, assignee=assignee)


def claim(*, ticket, actor) -> None:
    """An agent takes a ticket for themselves."""
    _assign_one(ticket, actor=actor, assignee=actor)


def assign(*, ticket, actor, assignee) -> None:
    """An agent gives a ticket to someone (possibly themselves)."""
    _assign_one(ticket, actor=actor, assignee=assignee)


def bulk_assign(*, ticket_ids, assignee, actor) -> list:
    """Hand a batch of tickets to one agent.

    Each ticket succeeds or fails on its own; one bad id does not undo the
    rest of the batch. Tickets that are waiting on the requester or already
    resolved change owner without changing status — sweeping "pending user"
    back into "in progress" would erase the fact that the ball is not ours.
    """
    results = []
    for ticket_id in ticket_ids:
        ticket = Ticket.objects.filter(pk=ticket_id, deleted_at__isnull=True).first()
        if ticket is None:
            results.append({"ticketId": ticket_id, "ok": False, "error": "not found"})
            continue
        try:
            _assign_one(ticket, actor=actor, assignee=assignee)
        except Exception as exc:  # one failure must not sink the batch
            results.append({"ticketId": ticket_id, "ok": False, "error": str(exc)})
        else:
            results.append({"ticketId": ticket_id, "ok": True})
    return results


# --------------------------------------------------------------------------
# T4 / T6 / T8 — status
# --------------------------------------------------------------------------

def mark_pending(*, ticket, actor) -> None:
    """T4: the ball goes back to the requester.

    Sends no email itself. The reply that asks the question carries the
    email; sending one here too would mean two emails for one action.
    """
    before_status = ticket.status
    with transaction.atomic():
        _add_message(
            ticket,
            message_type=TicketMessageType.SYSTEM,
            body=system_messages.MOVED_TO_PENDING_USER,
        )
        log_audit_event(
            actor=actor,
            entity_type=AUDIT_ENTITY_TYPE,
            entity_id=ticket.pk,
            action="status",
            before_state={"status": before_status},
            after_state={"status": TicketStatus.PENDING_USER},
        )
        _touch(ticket, user_visible=True, status=TicketStatus.PENDING_USER)


def resolve(*, ticket, actor) -> bool:
    """T6: mark the ticket resolved. Returns False if it already was.

    The guard is a conditional update rather than an ``if`` on the object in
    memory, so clicking Resolve twice cannot send the requester two "we're
    done" emails.
    """
    now = timezone.now()
    before_status = ticket.status
    changed = (
        Ticket.objects.filter(pk=ticket.pk)
        .exclude(status=TicketStatus.RESOLVED)
        .update(
            status=TicketStatus.RESOLVED,
            resolved_at=now,
            updated_at=now,
            support_updated_at=now,
        )
    )
    if not changed:
        return False

    ticket.status = TicketStatus.RESOLVED
    ticket.resolved_at = now
    ticket.updated_at = now
    ticket.support_updated_at = now

    with transaction.atomic():
        _add_message(
            ticket,
            message_type=TicketMessageType.SYSTEM,
            body=system_messages.RESOLVED,
        )
        log_audit_event(
            actor=actor,
            entity_type=AUDIT_ENTITY_TYPE,
            entity_id=ticket.pk,
            action="resolve",
            before_state={"status": before_status, "resolved_at": None},
            after_state={"status": TicketStatus.RESOLVED, "resolved_at": _iso(now)},
        )
        # The one email the client insisted must always go out, so it is also
        # the one whose failure gets written back to the timeline rather than
        # only into the logs.
        transaction.on_commit(lambda: emails.send_ticket_resolved(ticket))
    return True


def set_status(*, ticket, new_status, actor) -> bool:
    """T8: an agent corrects the status from the dropdown.

    Never touches the owner. Changing status and changing owner are separate
    controls, and giving one of them a hidden side effect on the other is how
    a ticket ends up assigned to someone who never saw it.

    Landing on resolved is the same act as T6, so it goes through resolve()
    and picks up the email. Landing back on open is deliberately *not*
    reopen(): reopen() is the path a requester's reply takes, and reusing it
    here would invent a reply they never wrote, file the audit row under
    their name, and email them about "your reply".
    """
    if new_status == TicketStatus.RESOLVED:
        return resolve(ticket=ticket, actor=actor)

    before_status = ticket.status
    if before_status == new_status:
        return False

    with transaction.atomic():
        _add_message(
            ticket,
            message_type=TicketMessageType.SYSTEM,
            body=system_messages.status_changed(new_status),
        )
        log_audit_event(
            actor=actor,
            entity_type=AUDIT_ENTITY_TYPE,
            entity_id=ticket.pk,
            action="status",
            before_state={"status": before_status},
            after_state={"status": new_status},
        )
        # resolved_at goes back to null so "time to resolve" is not computed
        # from a resolution that was undone.
        _touch(ticket, user_visible=True, status=new_status, resolved_at=None)
    return True
