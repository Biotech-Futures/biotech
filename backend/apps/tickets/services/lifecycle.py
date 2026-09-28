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
    OFF_THE_CLOCK_STATUSES,
    Ticket,
    TicketAttachment,
    TicketChannel,
    TicketMessage,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
)
from . import emails, system_messages
from .numbering import allocate_ticket_number

AUDIT_ENTITY_TYPE = "ticket"


class TicketGone(Exception):
    """The ticket was deleted while this request was still working on it.

    Views turn this into the same 404 they would have returned had the delete
    landed a moment earlier. It exists because the window is real: a request
    that uploads attachments spends seconds between reading the ticket and
    writing to it, and an admin can delete it in that gap.
    """


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


def _role_snapshot(user) -> str:
    """The requester's role name, frozen at submission time.

    Same reasoning as the region snapshot above. Read through
    RoleAssignmentHistory the way the admin app does, honouring valid_to so a
    lapsed assignment is not reported as current.

    Imported inside the function: apps.resources imports back into this
    dependency chain at module scope, and pulling it in at the top of a
    service the ticket app loads at startup is how that becomes a cycle.
    """
    if user is None:
        return ""
    from django.db.models import Q as _Q

    from apps.resources.models import RoleAssignmentHistory

    now = timezone.now()
    row = (
        RoleAssignmentHistory.objects.filter(user_id=user.pk)
        .filter(_Q(valid_to__isnull=True) | _Q(valid_to__gte=now))
        .select_related("role")
        .first()
    )
    return row.role.role_name if row else ""


def _lock(ticket) -> None:
    """Re-read the row under a row lock, in place.

    Callers hand us an instance fetched before the request did its slow work:
    a reply with attachments spends the upload to Azure holding an object
    whose status is already seconds old. Every function below decides what a
    state change *means* by reading that status, so it has to be the
    committed one, and it has to stay committed until this transaction ends.

    ``refresh_from_db`` rather than rebinding the name, because ``_touch``
    keeps the caller's own object honest by writing back onto the instance it
    was handed. Rebinding would point that at a different object.

    On SQLite the lock clause is a no-op, so the tests exercise the re-read
    and production gets the lock as well.

    Raises ``TicketGone`` if the row was deleted in the meantime. Every caller
    of this function is about to write to the ticket, and writing to a deleted
    one is worse than failing: the row is invisible to both the requester and
    the queue, so whatever we wrote lands where nobody can ever read it.
    """
    ticket.refresh_from_db(from_queryset=Ticket.objects.select_for_update())
    if ticket.deleted_at is not None:
        raise TicketGone(f"Ticket {ticket.pk} was deleted.")


def _touch(ticket, *, user_visible: bool, **extra):
    """Move the ticket's clocks, plus whatever else changed, in one write.

    ``user_visible`` decides whether the requester's clock moves too. It is
    False for everything that puts nothing new on the requester's timeline:
    internal notes, hand-offs between agents, priority and category changes.
    Moving their clock for an event with no timeline entry floats the ticket
    to the top of their list with nothing new to read, which tells them
    something is going on behind the scenes.

    "Nothing new on the timeline" is not the same as "they cannot see it".
    Since 2026-09-04 the requester chooses the priority and can see it on
    their own ticket, and they have always been able to see the category they
    chose. What stays False for those two is the *change*: it is a triage
    decision, not a message, so it belongs in the audit log and not in a
    person's inbox or at the top of their list.

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


def _last_system_message(ticket) -> str:
    """The last line the product wrote on this timeline in its own voice.

    System messages are the ones nobody signs, and every one of them reaches
    the requester: internal notes are a different message type and are
    stripped at the queryset before the timeline is serialised. Deleted rows
    are left out for the same reason ``_visible_messages`` leaves them out.
    What this answers is "what were they last told", not "what was ever
    written". The empty string on a ticket that has none, so callers can
    compare it without a null check.
    """
    return (
        ticket.messages.filter(
            message_type=TicketMessageType.SYSTEM, deleted_at__isnull=True
        )
        .order_by("-created_at", "-pk")
        .values_list("body", flat=True)
        .first()
        or ""
    )


# --------------------------------------------------------------------------
# T1 / T2 — a ticket comes into existence
# --------------------------------------------------------------------------

def create_ticket(
    *, user, category, subject, body, attachments=None, priority=None
) -> Ticket:
    """T1: someone submits the portal form.

    The number is allocated inside this transaction on purpose. If the insert
    fails the number goes back, rather than leaving a hole in the sequence
    that reads like a deleted ticket.

    ``priority`` is the requester's own answer to "how urgent is this?", added
    2026-09-04 when the client settled that "the person raising the enquiry
    (not necessarily a student) should be able to set a priority, but the
    support agent should be able to change it". It is optional so that every
    other caller — message screening, the tests, anything later — keeps the
    model default, and so that a form posted without the field still works.
    ``None`` means "they did not say", which is Normal.

    **No audit row, and that is the decision rather than an omission**
    (工单系统-完整说明.md §9.4, 03-state-machine.md §2 T1). The person who
    filled the form in is the record, and the ticket carries them in
    ``created_by``; there is nothing an audit row would add that the row it
    describes does not already hold. The screening entry point writes one
    (handoff.py) because there is no person on that path at all, so without it
    nothing would say where the ticket came from.

    The asymmetry this leaves is real and is worth knowing before changing it:
    the audit page's "Created" filter therefore answers with screening tickets
    only, which is why that page says so in its empty state rather than
    showing a bare empty table. T7's reopen row is not a counter-example — it
    is written for the p52 reopens figure, which is counted off it, and not
    because of who acted. T5, the same requester on the same ticket, writes
    none.
    """
    with transaction.atomic():
        ticket = Ticket.objects.create(
            ticket_number=allocate_ticket_number(),
            subject=subject,
            body=body,
            category=category,
            priority=priority or TicketPriority.NORMAL,
            region=_region_snapshot(user),
            requester_role=_role_snapshot(user),
            channel=TicketChannel.PORTAL,
            created_by=user,
            # The clock starts here. A brand new ticket is with support by
            # definition, and this is the client's step one: "Raised".
            awaiting_support_since=timezone.now(),
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
        #
        # robust=True because these hooks run inside the transaction block's
        # exit, which is still inside the caller's attachment-cleanup scope.
        # Without it, an email that fails to render propagates out past the
        # commit and the cleanup deletes blobs belonging to rows that are
        # already durable — a committed ticket whose attachment 404s forever.
        # A receipt that cannot be rendered is also simply not a reason to
        # fail a submission that already succeeded.
        transaction.on_commit(
            lambda: emails.send_ticket_submitted(ticket), robust=True
        )
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
        # The status on the instance predates the attachment upload. Read it
        # again under a lock: an agent resolving the ticket while the files
        # were going up would otherwise leave this reply on a resolved ticket
        # with no reopen, having promised the requester the opposite.
        _lock(ticket)
        message = _add_message(
            ticket,
            message_type=TicketMessageType.USER_MESSAGE,
            body=body,
            author=user,
            attachments=attachments,
        )
        # The requester has answered, so the ball is with support. Kept if it
        # is already running rather than restarted: somebody who writes three
        # messages in a row has been waiting since the first one, and
        # restarting the clock on each would hand support a fresh window every
        # time the person chased them.
        #
        # Read after _lock, so this is the committed value.
        awaiting = ticket.awaiting_support_since or timezone.now()

        if ticket.status == TicketStatus.RESOLVED:
            reopen(ticket=ticket, actor=user)
        elif ticket.status == TicketStatus.PENDING_USER:
            _add_message(
                ticket,
                message_type=TicketMessageType.SYSTEM,
                body=system_messages.status_changed(TicketStatus.IN_PROGRESS),
            )
            # No audit row. 03-state-machine.md §2 records T5 as "audit not
            # written" and gives the reason as "user action", and that reason
            # does not survive being read next to the row below it: T7 is the
            # requester acting too and writes a row. The difference that does
            # hold is whether anything reads it. T7's row is the source the
            # p52 reopens figure counts; nothing counts T5. The design table
            # still prints the old reason, so it needs the same correction.
            # The system message written just above is this transition's
            # record, and it is the book the requester can read for
            # themselves.
            #
            # The cost is a seam in the audit ledger: the status row before
            # this one ends on pending_user and the next one opens on
            # in_progress. Nothing computes a number from that chain, and the
            # timeline covers the missing step.
            #
            # resolved_at goes with the status, or a ticket that was resolved
            # and moved back keeps a resolution date that no longer happened.
            _touch(
                ticket,
                user_visible=True,
                status=TicketStatus.IN_PROGRESS,
                resolved_at=None,
                awaiting_support_since=awaiting,
            )
        else:
            _touch(ticket, user_visible=True, awaiting_support_since=awaiting)
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
            # Filed under the requester, because they are who triggered it.
            # This row exists where T5's does not because the p52 reopens
            # figure is counted off it (03-state-machine.md §2, T7), not
            # because of who acted: both transitions are the requester.
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
            # Back in the pool and back on the clock. A reopened ticket that
            # kept a null anchor would be one nobody could ever see go red,
            # which is the same defect the client asked us to fix.
            awaiting_support_since=timezone.now(),
        )


# --------------------------------------------------------------------------
# Support-side messages
# --------------------------------------------------------------------------

def add_support_reply(
    *, ticket, actor, body, attachments=None, move_to_pending=False
) -> TicketMessage:
    """An agent answers the requester.

    Also the only place ``first_response_at`` is set, and it is set with a
    conditional update rather than a read-then-write: two agents replying at
    the same moment would otherwise both see it empty and both write.

    ``move_to_pending`` folds T4 into this one action, which is what makes the
    "we are waiting on your answer" branch of ticket_reply.html reachable at
    all. That branch reads the status at send time, so while the admin app
    wrote the reply and changed the status as two requests, the status was
    still in_progress when the email was built and every "could you send us a
    screenshot?" rendered the other branch. Doing both here, before ``_touch``
    and inside the lock, means the email sees the status the agent intended.

    The same flag is also handed to the email as ``asked_for_information``.
    The status says the ticket is stopped and can say nothing about why, so
    without it the email cannot tell a question apart from an answer that
    happened to land on a ticket already waiting on the requester.

    Deliberately does not call ``mark_pending``: that would move the clocks
    twice and, because the email is scheduled here, is also how one action
    ends up sending two emails.
    """
    with transaction.atomic():
        # Same reason as the requester's reply: the attachments went up before
        # this ran, and an email is scheduled at the end. Sending "there is a
        # new reply on your enquiry" about a ticket that no longer exists is
        # the worst of the outcomes available here.
        _lock(ticket)
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

        moved = {}
        # ``ticket.status`` is the committed value: _lock re-read it above.
        # Skipping when it is already pending keeps a second reply from
        # stacking a duplicate system message on the timeline.
        if move_to_pending and ticket.status != TicketStatus.PENDING_USER:
            before_status = ticket.status
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
            moved["status"] = TicketStatus.PENDING_USER
            # resolved_at goes with the status, the same rule reopen(),
            # set_status() and the requester's reply all follow. Replying to a
            # resolved ticket to ask one more question would otherwise leave a
            # resolution date on a ticket that is no longer resolved, and
            # "time to resolve" is computed from that column.
            moved["resolved_at"] = None

        # Answered, so the clock stops. Passed as its own keyword and NOT
        # added to ``moved``: that dict is populated only inside the
        # move_to_pending branch above, so anything put in it is skipped on
        # the ordinary path — which is the default and what a plain Reply
        # does. A clear that lived in ``moved`` would leave every ordinary
        # reply on the clock forever, so every answered ticket would sit red
        # until it was resolved. That is the exact inverse of what the client
        # asked for, and no test that only exercises "reply and move to
        # pending" would notice.
        _touch(
            ticket,
            user_visible=True,
            awaiting_support_since=None,
            **moved,
        )
        # Sent from this one place, not from mark_pending() as well, or
        # "reply and move to pending" would send two emails for one action.
        #
        # ``move_to_pending`` and not ``moved``: the flag is the agent's own
        # answer to "have you asked them for something", and it is that
        # whatever the status turns out to be. A second question asked on a
        # ticket already waiting on the requester moves nothing, so ``moved``
        # is empty there while the agent has just asked for something. The
        # ticket records the status and nobody records the question, so this
        # is the only place the email can learn it.
        transaction.on_commit(
            lambda: emails.send_ticket_reply(
                ticket, asked_for_information=move_to_pending
            ),
            robust=True,
        )
    return message


def add_internal_note(*, ticket, actor, body, attachments=None) -> TicketMessage:
    """A note between agents. The requester must never learn it happened.

    Hence no email, no audit row, and only the support-side clock moves.
    """
    with transaction.atomic():
        _lock(ticket)
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

    Handing one back to the pool is the pick-up run backwards, so the status
    comes back with it. Without that the queue carried rows reading
    "In progress / Unassigned". The status column said somebody was on it and
    the owner column said nobody was, and the requester's own page went on
    telling them their ticket was being handled by a person who had put it
    down.

    The release is silent and the pick-up is not, which means the two are not
    a matched pair on the requester's timeline: after a release the sentence
    from the last pick-up is still the last thing they were told. So the
    announcement is made once per spell of being handled, not once per
    pick-up. Only the events that tell the requester the ticket stopped being
    handled put the next pick-up back on the record.
    """
    after_state = {"assignee_id": getattr(assignee, "pk", None)}

    with transaction.atomic():
        # Which of the two acts this is depends on the committed status, not
        # on whatever the queue page was showing when the agent clicked.
        _lock(ticket)
        before_state = {"assignee_id": ticket.assignee_id}
        # ``assignee is not None`` matters now that a ticket can be handed
        # back. Without it, releasing an open ticket reads as somebody picking
        # it up: the requester is told "your ticket is now being handled" and
        # the status moves to in progress, on a ticket that just lost its
        # owner and has nobody working it.
        picked_up_from_the_pool = (
            ticket.status == TicketStatus.OPEN and assignee is not None
        )
        # The other direction. Only out of "in progress": a ticket waiting on
        # the requester or already resolved is not made open again by losing
        # its owner, because the ball is not ours in either state.
        handed_back_to_the_pool = (
            ticket.status == TicketStatus.IN_PROGRESS and assignee is None
        )
        # Assigning a ticket to the person who already owns it changes
        # nothing, so it records nothing. Re-checked against the committed
        # value, the same rule the priority branch of the PATCH view follows:
        # another request may have set the same owner while this one waited
        # for the lock.
        #
        # Without this, two clicks on a name already in the dropdown wrote two
        # audit rows reading "assignee 11 -> assignee 11". Each one counted as
        # a hand-off on the p52 dashboard, printed as an unreadable
        # "Owner set to #11" on the audit page, and moved the support clock,
        # lifting the ticket to the top of the queue. A measure anybody can
        # inflate by clicking is not a measure.
        #
        # One exception, and it is the one case where "the owner is already
        # what you asked for" does not mean "there is nothing to do". The
        # assignee column is SET_NULL, so deleting an agent's account empties
        # it without touching the status and leaves the ticket the release
        # branch below exists to prevent: in progress with nobody on it.
        # Choosing Unassigned is then a no-op by this test and the ticket
        # could not be put right from the owner control at all. The condition
        # carries status == in progress with it, so an ordinary second click
        # on Unassigned still stops here.
        if before_state == after_state and not handed_back_to_the_pool:
            return

        # Saying it twice is not news. The release below is deliberately
        # silent, so claim -> release -> claim used to leave "your ticket is
        # now being handled" on the timeline twice with nothing between them,
        # and it repeated for as long as an agent kept clicking the owner
        # dropdown. Each repeat also moved the requester's clock and floated
        # the ticket to the top of their list. A sentence anybody can inflate
        # by clicking is not a sentence worth sending.
        #
        # Decided from what the requester was last told rather than from a
        # flag, which is what covers the doors either side of this one. A
        # reopen writes REOPENED, a resolve writes its own line, and an agent
        # correcting the status by hand writes another, so the pick-up after
        # any of those does announce itself again. In each of those cases the
        # ticket really did stop being handled and the requester was told so.
        # Only the silent release leaves the earlier sentence standing.
        tell_the_requester = (
            picked_up_from_the_pool
            and _last_system_message(ticket) != system_messages.TICKET_NOW_HANDLED
        )

        if tell_the_requester:
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
            # The owner and only the owner, per 03-state-machine.md §4. A
            # status this move may have carried with it is not recorded here:
            # the audit page summarises a row by the first field it
            # recognises, so a status key on an assign row would print the
            # status change and hide the change of owner the row exists for.
            before_state=before_state,
            after_state=after_state,
        )
        if picked_up_from_the_pool:
            _touch(
                ticket,
                # False on a re-claim the requester was not told about, for
                # the same reason the message was skipped: their clock is
                # what orders their own list, and nothing was added to their
                # timeline to justify moving it. The status they read is
                # still corrected.
                user_visible=tell_the_requester,
                assignee=assignee,
                status=TicketStatus.IN_PROGRESS,
            )
        elif handed_back_to_the_pool:
            # Silent, unlike the pick-up above, and the asymmetry is on
            # purpose. "Your ticket is now being handled" is a promise worth
            # making. "Nobody is on it just now" is not a sentence to send a
            # fourteen-year-old, and floating the ticket to the top of their
            # list would put it in front of them twice. The status on their
            # page is corrected either way, and the audit row written just
            # above is the support-side record of the release.
            #
            # awaiting_support_since is deliberately untouched, as it is on
            # every ownership change: the overdue clock started when the ball
            # came to support, and putting the ticket down does not hand it
            # back.
            _touch(
                ticket,
                user_visible=False,
                assignee=None,
                status=TicketStatus.OPEN,
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
    # Sorted so two overlapping batches take their row locks in the same
    # order. Unsorted, one batch holding 7 and waiting on 4 while another
    # holds 4 and waits on 7 is a deadlock.
    for ticket_id in sorted(ticket_ids):
        ticket = Ticket.objects.filter(pk=ticket_id, deleted_at__isnull=True).first()
        if ticket is None:
            results.append({"ticketId": ticket_id, "ok": False, "error": "not found"})
            continue
        try:
            _assign_one(ticket, actor=actor, assignee=assignee)
        except TicketGone:
            # The same condition as the branch above, found a moment later:
            # the row was there when the batch read it and was deleted before
            # this one took its lock. So it reads the same, and reporting it
            # any other way is what the queue page then shows the agent.
            #
            # ``str(exc)`` is what this used to append, and TicketGone carries
            # the database id. The page translates ticketId into the ticket
            # number the agent selected, so the reason arrived beside it
            # naming a second, internal number for the same ticket. Nothing on
            # that screen or in the queue prints database ids, so there was
            # nothing the reader could match it to.
            results.append({"ticketId": ticket_id, "ok": False, "error": "not found"})
        except Exception as exc:  # one failure must not sink the batch
            # Anything else really is unexpected, and its own text is the only
            # description of it there is. The queue page treats these as worth
            # retrying, which is why they must stay distinct from "not found".
            results.append({"ticketId": ticket_id, "ok": False, "error": str(exc)})
        else:
            results.append({"ticketId": ticket_id, "ok": True})
    return results


def soft_delete(*, ticket, actor) -> bool:
    """Take a ticket out of circulation. Returns False if it already was.

    What this is for: a duplicate, a test submission, or spam. Not for closing
    a real enquiry — that is what Resolved is, and a real enquiry deserves the
    email and the timeline entry that come with it.

    Deliberately admin-only at the view, and deliberately hidden from the
    requester as well as the queue: ``_my_tickets`` filters on the same column,
    so a deleted ticket leaves the student's list too. That is the point for a
    duplicate or a spam row, and it is why the endpoint is not handed to every
    agent (DEC-024).

    No timeline message and no email: there is nobody left to read either. The
    audit row is the whole record, which is why it carries enough of the
    ticket to identify it afterwards without joining to a row that no longer
    shows up in any queryset.
    """
    with transaction.atomic():
        # Snapshot from the committed row, not from the caller's instance: the
        # audit row is the only record that survives, so the status it names
        # has to be the one the ticket actually had.
        try:
            _lock(ticket)
        except TicketGone:
            return False
        # Read after the lock. Waiting for the row can take as long as the
        # writer in front takes to commit, and a clock read before that wait
        # stamps a moment earlier than everything this transaction then
        # writes, including its own audit row.
        now = timezone.now()
        changed = (
            Ticket.objects.filter(pk=ticket.pk, deleted_at__isnull=True)
            .update(deleted_at=now, support_updated_at=now)
        )
        if not changed:
            return False

        ticket.deleted_at = now
        ticket.support_updated_at = now
        log_audit_event(
            actor=actor,
            entity_type=AUDIT_ENTITY_TYPE,
            entity_id=ticket.pk,
            action="delete",
            before_state={
                "ticket_number": ticket.ticket_number,
                "subject": ticket.subject,
                "status": ticket.status,
                "created_by_id": ticket.created_by_id,
            },
            after_state={"deleted_at": _iso(now)},
        )
    return True


# --------------------------------------------------------------------------
# T4 / T6 / T8 — status
# --------------------------------------------------------------------------

def mark_pending(*, ticket, actor) -> None:
    """T4: the ball goes back to the requester.

    Sends no email itself. The reply that asks the question carries the
    email; sending one here too would mean two emails for one action.

    No production caller yet — the admin app splits T4 into "reply" then
    "change status" — but Phase 1a wires this logic into the reply path, and
    until this function matched the rest of the module it was a trap waiting
    there: the one state change with no row lock (so it would write onto a
    ticket deleted mid-request, recreating the DEC-024 race) and the one that
    left ``resolved_at`` behind (pending-user-with-a-resolution-date is a
    state the machine does not have, and it poisons the p52 resolution-time
    figures).
    """
    with transaction.atomic():
        _lock(ticket)
        before_status = ticket.status
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
        # resolved_at travels with the status, exactly as in set_status and
        # add_user_reply: a ticket moved off resolved must not keep reporting
        # a resolution that has been undone.
        _touch(
            ticket,
            user_visible=True,
            status=TicketStatus.PENDING_USER,
            resolved_at=None,
            # The ball is theirs now, so support is not on the clock. The
            # product tells the requester exactly this, both on their ticket
            # page and in the E2 email, and a red badge on the queue at the
            # same moment would be the product contradicting itself.
            awaiting_support_since=None,
        )


def resolve(*, ticket, actor) -> bool:
    """T6: mark the ticket resolved. Returns False if it already was.

    The guard is a conditional update rather than an ``if`` on the object in
    memory, so clicking Resolve twice cannot send the requester two "we're
    done" emails.
    """
    # One transaction around the whole thing. The conditional update still
    # decides who wins — a concurrent caller blocks on the row lock and then
    # re-evaluates its condition against the committed row, matching nothing
    # — but now the status, the timeline entry and the audit row land
    # together. Split across two transactions, a crash in the gap left a
    # ticket the queue calls resolved with nothing on its timeline saying so.
    with transaction.atomic():
        # Taken for the same reason as every other write path, and it took a
        # full-coverage pass to notice this one did not have it. Two separate
        # defects came out of the gap:
        #
        #   * A ticket deleted between the view fetching it and this line ran
        #     the conditional update, matched nothing, returned False, and the
        #     view reported "Ticket updated successfully" with a 200 while the
        #     ticket sat untouched. Every other write path raised TicketGone
        #     here and the view turned that into a 404.
        #   * before_status was read off the caller's instance, which predates
        #     the request's own slow work, so the audit row could record a
        #     transition out of a status the ticket had already left.
        #
        # Both are the same root cause: deciding what this change *means* from
        # an uncommitted read. _lock re-reads under the row lock and raises
        # TicketGone on a deleted row, so read before_status after it.
        _lock(ticket)
        before_status = ticket.status
        # Read after the lock, for the same reason as soft_delete: a resolve
        # that queued behind a reply used to stamp resolved_at earlier than
        # the first_response_at of the reply it lost the race to, so the
        # ticket read as resolved before it was ever answered.
        now = timezone.now()
        changed = (
            # Redundant with _lock above and kept deliberately: this update is
            # the thing that decides whether the "we're done" email goes out,
            # and it must not go out about a ticket the requester can no
            # longer open.
            Ticket.objects.filter(pk=ticket.pk, deleted_at__isnull=True)
            .exclude(status=TicketStatus.RESOLVED)
            .update(
                status=TicketStatus.RESOLVED,
                resolved_at=now,
                updated_at=now,
                support_updated_at=now,
                # Done, so nobody is waiting. Written here rather than through
                # _touch because this path deliberately uses a conditional
                # update to decide the winner of two concurrent Resolve
                # clicks.
                awaiting_support_since=None,
            )
        )
        if not changed:
            return False

        ticket.status = TicketStatus.RESOLVED
        ticket.resolved_at = now
        ticket.updated_at = now
        ticket.support_updated_at = now
        ticket.awaiting_support_since = None

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
        transaction.on_commit(lambda: emails.send_ticket_resolved(ticket), robust=True)
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

    with transaction.atomic():
        _lock(ticket)
        before_status = ticket.status
        if before_status == new_status:
            return False
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
        # The clock has to move in BOTH directions here, and the second one
        # is easy to miss.
        #
        # Into "pending user": stop it, same as mark_pending.
        #
        # Out of "pending user" and back to open or in progress: start it. The
        # ordinary case is a requester who answered some other way — rang up,
        # caught someone in a workshop — and an agent correcting the status by
        # hand. Nothing else on this path sets the anchor, so without this the
        # ticket would sit with support, ageing, and be structurally incapable
        # of ever going red. That is precisely the one-shot behaviour the
        # client rejected, arriving through a different door.
        #
        # Kept if already running, for the same reason as add_user_reply.
        #
        # Three cases, and getting the middle one's width right took two
        # goes in opposite directions.
        #
        # Written first as a plain `else`, it re-armed on ANY change that was
        # not into "pending user" — including the ordinary open -> in progress
        # an agent makes after answering. The anchor is null at that moment
        # precisely because they answered, so `or now()` put an answered
        # ticket back on the clock and it went red four hours later with the
        # requester having said nothing.
        #
        # Narrowed to "out of pending user" only, it then missed the other way
        # back in: an agent who resolves a ticket by mistake and corrects it
        # from the dropdown. resolve() clears the anchor, so the ticket landed
        # in "in progress", sitting with support, structurally unable ever to
        # go red — the same defect, one door along. (The requester's own reply
        # on a resolved ticket goes through reopen(), which sets the anchor
        # itself; this is the agent-triggered path.)
        #
        # The rule underneath both mistakes: support is off the clock in
        # exactly two states, so the clock restarts when a ticket leaves
        # either of them for one where the ball is ours again.
        if new_status in OFF_THE_CLOCK_STATUSES:
            awaiting = None
        elif before_status in OFF_THE_CLOCK_STATUSES:
            awaiting = ticket.awaiting_support_since or timezone.now()
        else:
            awaiting = ticket.awaiting_support_since

        # resolved_at goes back to null so "time to resolve" is not computed
        # from a resolution that was undone.
        _touch(
            ticket,
            user_visible=True,
            status=new_status,
            resolved_at=None,
            awaiting_support_since=awaiting,
        )
    return True
