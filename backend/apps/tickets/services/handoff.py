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

from ..models import Ticket, TicketChannel, TicketMessageType, TicketPriority
from .numbering import allocate_ticket_number

# ⚠️ OPEN POINT, awaiting a call from Jinqi.
#
# Ticket.category is required, but the screening handoff contract never says
# what an AI-raised ticket should carry. The three categories on offer
# (Account & Access, Programs & Groups, Certificates & Records) are self-serve
# topics a *requester* picks; a child-safety flag is none of them, and filing
# it under one would corrupt the category breakdown the client asked for on
# p52. Left empty for now, which costs nothing to change later: there is no
# production data, so adding a fourth choice stays a one-line edit plus a
# choices-only migration for as long as this is unmerged.
SCREENING_TICKET_CATEGORY = ""

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
        )
        # One system message, not two: the acknowledgement T1 writes exists to
        # reassure a requester, and this ticket has none.
        ticket.messages.create(
            author=None,
            message_type=TicketMessageType.SYSTEM,
            body=_evidence_body(
                ticket,
                message=message,
                verdict=verdict,
                text_snapshot=text_snapshot,
                group=group,
                sender=sender,
            ),
        )
    return ticket
