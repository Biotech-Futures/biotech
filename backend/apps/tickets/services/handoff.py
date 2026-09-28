"""The one function the AI screening module is allowed to call.

🔒 FROZEN INTERFACE. The signature below appears verbatim in three documents
(.capstone/design/screening/05-ticket-handoff.md §1,
 .capstone/design/ticketing/02-data-model.md §5, and the T2 row of
 .capstone/design/ticketing/03-state-machine.md). Changing it means changing
all three and telling whoever owns the screening module.

Direction of the contract: screening hands us a verdict, we decide what goes
in the ticket. The screening app imports this and implements nothing; it
never touches the tickets tables.
"""

from django.db import transaction
from django.utils import timezone

from apps.audit.services import log_audit_event

from ..models import (
    Ticket,
    TicketCategory,
    TicketChannel,
    TicketMessageType,
    TicketPriority,
)
from .lifecycle import AUDIT_ENTITY_TYPE
from .numbering import allocate_ticket_number

# Ticket.category is required, and the screening handoff contract never said
# what an AI-raised ticket should carry. The categories on offer to a
# requester (the client's eight, from Account and access to Other) are
# self-serve topics a person picks for themselves; a child-safety flag is none
# of them, and filing it under one would corrupt the category breakdown the
# client asked for on p52.
#
# It used to be the empty string, which had two costs a demo would surface
# immediately: the admin panel showed "Not categorised", and the queue's
# category filter skips falsy values, so screening tickets could not be
# filtered for at all. A fourth choice, never offered to requesters, fixes
# both and gives the p52 breakdown an honest bucket to count.
SCREENING_TICKET_CATEGORY = TicketCategory.FLAGGED_CONTENT

# Judged on which layer produced the verdict, never on whether an LLM key is
# configured. A configured LLM that times out or returns unparseable JSON
# falls back to the rule layer, and those tickets are Normal like any other
# rule hit — reading the key instead would mark the whole fallback path High
# and, with it, drag the overdue threshold from three days down to one.
_PRIORITY_BY_LAYER = {
    "llm": TicketPriority.HIGH,
    "rule": TicketPriority.NORMAL,
}

# The subject has to fit CharField(255). The fixed part is at most 49
# characters and a group name can be 255 on its own, so an untruncated
# subject can reach 304 — which does not fail politely: the insert raises,
# and it shares a transaction with the screening record, so the whole batch
# rolls back.
_MAX_GROUP_NAME_IN_SUBJECT = 200


def _truncate_group_name(group_name: str) -> str:
    group_name = group_name or ""
    if len(group_name) <= _MAX_GROUP_NAME_IN_SUBJECT:
        return group_name
    return group_name[:_MAX_GROUP_NAME_IN_SUBJECT] + "…"


def _display_name(user) -> str:
    if user is None:
        return "Unknown sender"
    name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    return name or getattr(user, "email", "") or "Unknown sender"


def _region_snapshot(user) -> str:
    return getattr(getattr(user, "country", None), "country_name", "") or ""


def _evidence_body(ticket, *, message, verdict, text_snapshot, group, sender) -> str:
    from django.conf import settings

    group_name = getattr(group, "group_name", "") or "Unknown group"
    group_id = getattr(group, "pk", None)
    admin_base = getattr(settings, "ADMIN_FRONTEND_BASE_URL", "").rstrip("/")

    lines = [
        "A message was flagged by automated screening.",
        "",
        f"Group: {group_name} (group id {group_id})",
        f"Sender: {_display_name(sender)}",
        f"Detected by: {getattr(verdict, 'layer', '') or 'unknown'} layer",
        f"Category: {getattr(verdict, 'category', '') or 'uncategorised'}",
        f"Reason: {getattr(verdict, 'reason', '') or 'not given'}",
        "",
        "Message as it read when it was flagged:",
        text_snapshot or "",
        "",
        "Review it here:",
        # The queue page opens the detail as a slide-over panel rather than
        # its own route, so this link only works if that panel honours
        # ?ticket=<id>. W7 owns that.
        f"1. This ticket: {admin_base}/tickets?ticket={ticket.pk}",
        # Group messages are a modal inside the admin groups list and have no
        # address of their own, so this half is directions rather than a link.
        f"2. The conversation: Admin → Groups → {group_name} "
        f"(group id {group_id}) → Messages",
    ]
    return "\n".join(lines)


def create_ticket_from_screening(message, verdict, text_snapshot) -> Ticket:
    """Raise a support ticket for a message the screener flagged.

    Called in-process from the screening pipeline, not over HTTP.

    ``text_snapshot`` is passed in rather than read back off ``message``
    because the author may have edited it since. Reading it fresh would file
    the edited text as evidence for a judgement made about the original.

    Sends nothing. There is no requester on these tickets, so every email in
    the system skips them for their whole life, not just at creation.

    Writes an audit row with no actor. Note this is deliberately NOT
    symmetric with portal submission, which writes none: a person filling in
    a form is their own record, and the ticket itself is the evidence. This
    path has no person in it at all. A machine judged a message a minor wrote
    and raised a case about it, so "what was flagged, by which layer, and
    when" has to stay answerable even after the message is edited or the
    ticket is closed.
    """
    group = getattr(message, "group", None)
    sender = getattr(message, "sender_user", None)
    group_name = getattr(group, "group_name", "") or ""
    category = getattr(verdict, "category", "") or "uncategorised"
    layer = getattr(verdict, "layer", "") or ""

    subject = (
        f'AI screening: {category} — group "{_truncate_group_name(group_name)}"'
    )

    with transaction.atomic():
        ticket = Ticket.objects.create(
            ticket_number=allocate_ticket_number(),
            subject=subject,
            body=text_snapshot or "",
            category=SCREENING_TICKET_CATEGORY,
            region=_region_snapshot(sender),
            channel=TicketChannel.AI_SCREENING,
            priority=_PRIORITY_BY_LAYER.get(layer, TicketPriority.NORMAL),
            created_by=None,
            # On the clock from the moment it is raised, exactly like a ticket
            # a person submitted. These have no requester to reply to them, so
            # the only thing that can ever stop the clock is an agent
            # answering or resolving — which is right: a flagged message
            # nobody has looked at is the case that most needs to go red.
            #
            # It also has to be set here rather than derived from the
            # timeline, because a screening ticket carries no user_message at
            # all: its only row is the internal note below.
            awaiting_support_since=timezone.now(),
        )
        # One system message, not two: the acknowledgement T1 writes exists to
        # reassure a requester, and this ticket has none.
        # INTERNAL_NOTE, not SYSTEM. SYSTEM is the type the requester is meant
        # to read — "we are looking into this", "this has been resolved" — and
        # views.py excludes only internal notes from their timeline. This body
        # is a case file: it names the sender (falling back to their email
        # address), quotes the flagged private message word for word, and
        # links into the admin app.
        #
        # It is not reachable today, because these tickets are created with
        # created_by=None and the requester's queryset filters on ownership.
        # That guard is real and tested, but it says "this ticket has no
        # owner" when what has to be true is "this text is never shown to a
        # requester". Those come apart the moment anything gives a screening
        # ticket an owner. Same correction as the delivery-failure notice
        # (DEC-026 ⑤), and the content here is more sensitive.
        ticket.messages.create(
            author=None,
            message_type=TicketMessageType.INTERNAL_NOTE,
            body=_evidence_body(
                ticket,
                message=message,
                verdict=verdict,
                text_snapshot=text_snapshot,
                group=group,
                sender=sender,
            ),
        )
        log_audit_event(
            # No actor: the screener is not a person. AuditLog.actor_user is
            # nullable, so this records as a system action rather than being
            # attributed to whoever happened to trigger the batch.
            actor=None,
            entity_type=AUDIT_ENTITY_TYPE,
            entity_id=ticket.pk,
            action="create",
            before_state=None,
            after_state={
                "ticket_number": ticket.ticket_number,
                "channel": TicketChannel.AI_SCREENING,
                "priority": ticket.priority,
                "screening_layer": layer,
                "screening_category": category,
                "message_id": getattr(message, "pk", None),
            },
        )
    return ticket
