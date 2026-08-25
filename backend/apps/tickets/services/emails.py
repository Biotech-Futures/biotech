"""The three emails a requester can receive about their ticket.

Support agents get none. They work from the queue, so mailing them as well
would be noise nobody reads (DEC-009).

Each email carries the same three things, because a ticket update that does
not say them leaves the requester guessing: where the ticket stands, whose
move it is next, and roughly when to expect a reply.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from apps.services.email_branding import attach_inline_logo, brand_context
from apps.services.mailer import send_async

from ..models import TicketStatus

logger = logging.getLogger(__name__)

# Where the requester reads their ticket. Hash routing, matching the rest of
# the user app. The page itself arrives with the Vue work; the shape is fixed
# here so the link does not have to change when it does.
def _ticket_url(ticket) -> str:
    base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    return f"{base}/#/support/tickets/{ticket.pk}"


def _recipient(ticket):
    """Who to write to, or None if there is nobody.

    Nobody is a real and expected case: tickets raised by message screening
    have no requester at all. That is not an error, and it must not be
    treated as one — it just means the whole email is skipped.
    """
    return getattr(ticket.created_by, "email", "") or None


def _context(ticket, **extra):
    return {
        **brand_context(),
        "TICKET_NUMBER": ticket.ticket_number,
        "TICKET_SUBJECT": ticket.subject,
        "TICKET_URL": _ticket_url(ticket),
        "STATUS_LABEL": TicketStatus(ticket.status).label,
        "FIRST_NAME": getattr(ticket.created_by, "first_name", "") or "",
        **extra,
    }


def _dispatch(ticket, *, template, subject, kind, text_body, context=None, on_failure=None) -> bool:
    # These all run after the transaction commits, so re-read: the email must
    # describe the ticket that exists, not the one the caller was holding.
    try:
        ticket.refresh_from_db()
    except ticket.__class__.DoesNotExist:
        logger.info("ticket_email.skipped kind=%s reason=ticket_gone", kind)
        return False

    to = _recipient(ticket)
    if not to:
        logger.info(
            "ticket_email.skipped kind=%s ticket=%s reason=no_recipient",
            kind, ticket.ticket_number,
        )
        return False

    ctx = _context(ticket, **(context or {}))
    html_body = render_to_string(f"emails/{template}", ctx)
    msg = EmailMultiAlternatives(
        subject=subject.format(**ctx),
        body=text_body.format(**ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
    )
    msg.attach_alternative(html_body, "text/html")
    attach_inline_logo(msg)
    send_async(msg, kind=kind, on_failure=on_failure)
    return True


def send_ticket_submitted(ticket) -> bool:
    """E1. Sent once, when the ticket is created."""
    return _dispatch(
        ticket,
        template="ticket_submitted.html",
        subject="{BRAND_CONNECT}: we have your enquiry ({TICKET_NUMBER})",
        kind="ticket_submitted",
        text_body=(
            "Thanks for getting in touch.\n\n"
            "Your enquiry {TICKET_NUMBER} is open and with our support team. "
            "You do not need to do anything for now. We usually reply within "
            "one business day.\n\n"
            "Subject: {TICKET_SUBJECT}\n"
            "View your enquiry: {TICKET_URL}\n"
        ),
    )


def send_ticket_reply(ticket) -> bool:
    """E2. Sent when support answers.

    Sent from one place only. If it also went out when a ticket was moved to
    "pending user", replying and moving in one action would send two.
    """
    waiting_on_requester = ticket.status == TicketStatus.PENDING_USER
    return _dispatch(
        ticket,
        template="ticket_reply.html",
        subject="{BRAND_CONNECT}: an update on your enquiry ({TICKET_NUMBER})",
        kind="ticket_reply",
        context={"WAITING_ON_REQUESTER": waiting_on_requester},
        text_body=(
            "There is a new reply on your enquiry {TICKET_NUMBER}.\n\n"
            "Status: {STATUS_LABEL}\n"
            "Subject: {TICKET_SUBJECT}\n\n"
            "Read it and reply here: {TICKET_URL}\n"
        ),
    )


def send_ticket_resolved(ticket) -> bool:
    """E3. Sent when the ticket is resolved.

    The one email the client asked for by name. If it fails to send, the
    ticket stays resolved and the failure is written onto the timeline where
    an agent can see it and follow up (DEC-012). Rolling the status back
    instead would mean an agent's click quietly undoing itself minutes later
    because of a mail relay.
    """
    recipient = _recipient(ticket)
    return _dispatch(
        ticket,
        template="ticket_resolved.html",
        subject="{BRAND_CONNECT}: your enquiry is resolved ({TICKET_NUMBER})",
        kind="ticket_resolved",
        text_body=(
            "Your enquiry {TICKET_NUMBER} has been marked as resolved.\n\n"
            "Subject: {TICKET_SUBJECT}\n\n"
            "If this is not sorted, reply on the enquiry and it will reopen "
            "automatically: {TICKET_URL}\n"
        ),
        on_failure=_record_delivery_failure(ticket.pk, recipient),
    )


def _record_delivery_failure(ticket_id, recipient):
    """Put a failed resolution email somewhere a person will see it.

    Runs on the mail worker thread, so it does its own database work and
    takes nothing from the request that triggered it.
    """

    def _callback(_exc):
        # Imported here rather than at module scope: lifecycle imports this
        # module to send, so importing it back at the top would be a cycle.
        from ..models import TicketMessage, TicketMessageType
        from . import lifecycle, system_messages
        from ..models import Ticket

        ticket = Ticket.objects.filter(pk=ticket_id).first()
        if ticket is None:
            return
        TicketMessage.objects.create(
            ticket=ticket,
            message_type=TicketMessageType.SYSTEM,
            body=system_messages.email_delivery_failed(recipient or "the requester"),
        )
        # Support-side only. A bounced email is not something to float to the
        # top of the requester's list.
        lifecycle._touch(ticket, user_visible=False)

    return _callback
