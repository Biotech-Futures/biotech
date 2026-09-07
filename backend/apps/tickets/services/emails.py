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


# How long we tell a requester to expect to wait. p51 asks every notification
# to carry the current status, the next action, and the expected response;
# this is the third of those, and it was only ever written into E1.
#
# One string used by all three emails and by both halves of each, because the
# failure mode here is drift: three templates and three plain-text bodies
# quoting three different waits is worse than quoting none. It is copy, not
# the SLA — TICKET_SLA_* drives the Overdue badge, is measured in hours and
# varies by priority, and putting "four hours" in front of a requester would
# promise them the internal target for a high-priority ticket they cannot see
# the priority of.
EXPECTED_REPLY = "one business day"

# Who the email is from, in the requester's own words. A team and never a
# person: DEC-017 settled that nothing sent to a requester names the agent
# working their ticket, because the requesters are minors. The portal shows
# support replies as "Support" for the same reason, so this matches what they
# already see there.
#
# Written once and used by both halves of all three emails. The HTML half
# takes it from _ticket_signoff.html; this is the plain-text twin, and the two
# are pinned to say the same thing by test_emails.
#
# A function and not a constant, and that is the whole point. It used to be a
# string holding "{BRAND_NAME}", interpolated into text_body which is then run
# through one str.format — and str.format does not recurse, so the inner
# placeholder was never expanded and every student received the literal text
# "The {BRAND_NAME} support team". Resolving it here, against the same
# brand_context the HTML half uses, means there is no second round of
# formatting to forget.
def _sign_off(ctx) -> str:
    return f"Thanks,\nThe {ctx['BRAND_NAME']} support team"


def _context(ticket, **extra):
    first_name = getattr(ticket.created_by, "first_name", "") or ""
    ctx = {
        **brand_context(),
        "TICKET_NUMBER": ticket.ticket_number,
        "TICKET_SUBJECT": ticket.subject,
        "TICKET_URL": _ticket_url(ticket),
        "STATUS_LABEL": TicketStatus(ticket.status).label,
        "FIRST_NAME": first_name,
        # Already resolved, so the plain-text bodies can interpolate it with
        # str.format the way the templates use |default. An account invited by
        # an administrator and never completed has no first name at all, and
        # "Hi ," at the top of an email to a fifteen-year-old reads as broken.
        "GREETING_NAME": first_name or "there",
        "EXPECTED_REPLY": EXPECTED_REPLY,
        **extra,
    }
    ctx["SIGN_OFF"] = _sign_off(ctx)
    return ctx


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
            "Hi {GREETING_NAME},\n\n"
            "Thanks for getting in touch.\n\n"
            "Your enquiry {TICKET_NUMBER} is open and with our support team. "
            "You do not need to do anything for now. We usually reply within "
            "{EXPECTED_REPLY}.\n\n"
            "Subject: {TICKET_SUBJECT}\n"
            "View your enquiry: {TICKET_URL}\n\n"
            "{SIGN_OFF}\n"
        ),
    )


def send_ticket_reply(ticket, *, asked_for_information=False) -> bool:
    """E2. Sent when support answers.

    Sent from one place only. If it also went out when a ticket was moved to
    "pending user", replying and moving in one action would send two.

    Two inputs, from two different places, because one of them cannot answer
    for the other:

    * ``WAITING_ON_REQUESTER`` reads the status at send time. It says whether
      the ticket is stopped, which the status does prove. It is trustworthy
      only because ``add_support_reply`` moves the ticket to "pending user"
      inside the same transaction as the reply: while those were two
      requests, the status was still in_progress here and an agent asking a
      question rendered the branch for a ticket nobody was waiting on.
    * ``asked_for_information`` is the action the agent took, passed down by
      ``add_support_reply`` from the "I have asked them for something" box.
      Nothing on the ticket records it. A ticket stays in "pending user"
      until something moves it out, so a later reply that answers in full
      finds exactly the same status, and for as long as the status was the
      only input neither branch could say "we have asked you for something"
      without saying it on those replies too.

    Keeping them apart is what lets the main case say the useful thing again.
    The status is the outer test, so a reply whose status moved back under it
    between commit and send falls to the wording that needs no status at all.

    Both halves of the email branch. The plain-text alternative is what a
    text-only client renders, and it used to carry one fixed sentence for
    both cases, so the half of the audience that never sees the HTML would
    still be missing the one fact that matters.
    """
    waiting_on_requester = ticket.status == TicketStatus.PENDING_USER
    if waiting_on_requester and asked_for_information:
        closing = (
            "We have asked you for some more information. The enquiry is "
            "waiting on your answer, so nothing further will happen until "
            "you reply: {TICKET_URL}\n\n"
            "Once you reply, we usually come back within {EXPECTED_REPLY}.\n"
        )
    elif waiting_on_requester:
        closing = (
            "The enquiry is still waiting on your answer, so nothing further "
            "will happen until you reply: {TICKET_URL}\n\n"
            "Once you reply, we usually come back within {EXPECTED_REPLY}.\n"
        )
    else:
        closing = (
            "Read it and reply there if we have asked you for anything: "
            "{TICKET_URL}\n\n"
            "If you reply, we usually come back within {EXPECTED_REPLY}.\n"
        )
    return _dispatch(
        ticket,
        template="ticket_reply.html",
        subject="{BRAND_CONNECT}: an update on your enquiry ({TICKET_NUMBER})",
        kind="ticket_reply",
        context={
            "WAITING_ON_REQUESTER": waiting_on_requester,
            "ASKED_FOR_INFORMATION": waiting_on_requester and asked_for_information,
        },
        text_body=(
            "Hi {GREETING_NAME},\n\n"
            "There is a new reply on your enquiry {TICKET_NUMBER}.\n\n"
            "Status: {STATUS_LABEL}\n"
            "Subject: {TICKET_SUBJECT}\n\n"
            + closing
            + "\n{SIGN_OFF}\n"
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
            "Hi {GREETING_NAME},\n\n"
            "Your enquiry {TICKET_NUMBER} has been marked as resolved.\n\n"
            "Subject: {TICKET_SUBJECT}\n\n"
            "If this is not sorted, reply on the enquiry and it will reopen "
            "automatically: {TICKET_URL}\n\n"
            "If you do, we usually come back within {EXPECTED_REPLY}.\n\n"
            "{SIGN_OFF}\n"
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
            message_type=TicketMessageType.INTERNAL_NOTE,
            body=system_messages.email_delivery_failed(recipient or "the requester"),
        )
        # An internal note, not a SYSTEM message. The original design said
        # SYSTEM (DEC-012, 05-conversation-model.md §1), and that turned out
        # to be a decision written without noticing where SYSTEM lands:
        # views.py excludes only internal notes from the requester's view, so
        # a sentence addressed to an agent — "could not be delivered, please
        # follow up", carrying the requester's own email address — was being
        # shown to the requester on their own page.
        #
        # DEC-012's stated purpose is to expose the failure to support so a
        # person can resend by hand. INTERNAL_NOTE delivers exactly that and
        # nothing more: agents still see it in the same timeline, and the
        # person whose address it names does not.
        #
        # The _touch is support-side for the same reason it always was: a
        # bounce is not something to float to the top of the requester's list.
        lifecycle._touch(ticket, user_visible=False)

    return _callback
