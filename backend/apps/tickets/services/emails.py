"""The emails about support enquiries.

Three go to the requester, and each carries the same three things, because a
ticket update that does not say them leaves the requester guessing: where the
ticket stands, whose move it is next, and roughly when to expect a reply.

Three go to the support inbox, not to any one agent. DEC-009 had said support
gets nothing, since agents work from the queue; the client asked at the
8 October meeting for "emails to go to our support inbox to say like there is
a new inquiry" (C-17) and for a regular count of what is still open (C-18),
and on 20 October for one when the AI screening flags a message. They go to
one shared address, TICKET_SUPPORT_INBOX, so DEC-009's point still holds for
the agents themselves.

All six go through System Emails (_send_system): the support inbox's at the
client's request of 20 October, the requester's at Jinqi's of 22 October.
"""

import logging
from email.utils import parseaddr

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from apps.services.email_branding import brand_context
from apps.services.system_email import SENT, SKIPPED, send_system_email, sender_for

from ..models import TicketCategory, TicketPriority, TicketStatus

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
        # The footer's "Add <address> to your address book" line has to name
        # the mailbox these emails really come from, and they come from
        # support@ (TICKET_FROM_EMAIL), not the info@ brand_context() gives
        # every other email on the platform. Read off the From value itself so
        # the header and the footer cannot name two different mailboxes.
        "SENDER_EMAIL": parseaddr(settings.TICKET_FROM_EMAIL)[1],
        "TICKET_NUMBER": ticket.ticket_number,
        "TICKET_SUBJECT": ticket.subject,
        "TICKET_URL": _ticket_url(ticket),
        "STATUS_LABEL": TicketStatus(ticket.status).label,
        # The template picks the status style on this and not on the label.
        # The label is copy and may be reworded; the key is what the ticket
        # actually stores.
        "STATUS_KEY": ticket.status,
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
    ctx["STATUS_PILL"] = _status_pill(ticket.status)
    return ctx


def _status_pill(status) -> str:
    """The status as the coloured pill the emails show, finished here and not
    in the template; _ticket_status_pill.html says why."""
    return mark_safe(render_to_string("emails/_ticket_status_pill.html", {
        "STATUS_KEY": status,
        "STATUS_LABEL": TicketStatus(status).label,
    }).strip())


def _send_system(key, to, ctx, text_body, on_failure=None) -> str:
    """One ticket email, sent through System Emails.

    Since 20 and 22 October all six are on it (apps.services.email_registry),
    which reverses DEC-042. So they go the way every system email goes
    (apps.services.system_email): switched off there, or paused for the whole
    site, they are not sent; wording an admin saves there is what goes out,
    else the template file; the mailbox picked there sends it, "support"
    (support@) unless changed, which is the address the client asked enquiry
    mail to come from; and each send is noted in its Log.

    ``text_body`` is the plain-text half for when the wording is the template
    file's; saved wording brings its own. ``on_failure`` is called if the send
    is a miss (E3's note on the ticket). Returns SENT (handed to the mail
    pool), SKIPPED (switched off) or FAILED.
    """
    # The footer asks the reader to add the sending address to their address
    # book, so it has to name the mailbox System Emails will really send from.
    ctx = {**ctx, "SENDER_EMAIL": sender_for(key).address}
    return send_system_email(
        key,
        to,
        ctx,
        default_text=text_body.format(**ctx),
        background=True,
        on_failure=on_failure,
    )


def _dispatch(ticket, *, key, text_body, context=None, on_failure=None) -> bool:
    """One of the three to the requester. True if it was handed to the mail pool."""
    # These all run after the transaction commits, so re-read: the email must
    # describe the ticket that exists, not the one the caller was holding.
    try:
        ticket.refresh_from_db()
    except ticket.__class__.DoesNotExist:
        logger.info("ticket_email.skipped kind=%s reason=ticket_gone", key)
        return False

    to = _recipient(ticket)
    if not to:
        logger.info(
            "ticket_email.skipped kind=%s ticket=%s reason=no_recipient",
            key, ticket.ticket_number,
        )
        return False

    ctx = _context(ticket, **(context or {}))
    return _send_system(key, to, ctx, text_body, on_failure=on_failure) == SENT


def send_ticket_submitted(ticket) -> bool:
    """E1. Sent once, when the ticket is created."""
    return _dispatch(
        ticket,
        key="ticket_submitted",
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
      ``add_support_reply``: the reply was sent with "Pending user" chosen
      beside it (the old "I have asked them for something" box, a status
      dropdown since C-19). Nothing on the ticket records it. A ticket stays in "pending user"
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
    flags = {
        "WAITING_ON_REQUESTER": waiting_on_requester,
        "ASKED_FOR_INFORMATION": waiting_on_requester and asked_for_information,
    }
    # The HTML half's next step, picked here for the reason in
    # _ticket_reply_next_step.html.
    next_step = mark_safe(render_to_string(
        "emails/_ticket_reply_next_step.html", {**flags, "EXPECTED_REPLY": EXPECTED_REPLY},
    ).strip())
    return _dispatch(
        ticket,
        key="ticket_reply",
        context={**flags, "NEXT_STEP": next_step},
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
        key="ticket_resolved",
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


# --------------------------------------------------------------------------
# To the support inbox
# --------------------------------------------------------------------------

# The words the requester chose from, as the portal's form offers them
# (frontend/src/utils/supportAPI.ts, TICKET_PRIORITIES). The inbox sees both:
# what the requester said and the queue's own level for it.
URGENCY_WORDS = {
    TicketPriority.HIGH: "I cannot continue",
    TicketPriority.NORMAL: "I can keep working",
    TicketPriority.LOW: "It can wait",
}


def _support_queue_url(ticket=None) -> str:
    """The queue in the portal, opened on one ticket when there is one."""
    base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    return f"{base}/#/admin/tickets" + (f"?ticket={ticket.pk}" if ticket is not None else "")


def _name(user) -> str:
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email


def _send_to_support(key, ctx, text_body) -> str:
    """One of the support inbox's three; see _send_system."""
    return _send_system(key, settings.TICKET_SUPPORT_INBOX, ctx, text_body)


def _fresh(ticket, key):
    """The ticket as committed, or None if it has gone since.

    These run after the transaction commits, so re-read: the email must
    describe the ticket that exists, not the one the caller was holding.
    """
    try:
        ticket.refresh_from_db()
    except ticket.__class__.DoesNotExist:
        logger.info("ticket_email.skipped kind=%s reason=ticket_gone", key)
        return None
    return ticket


def _support_ticket_context(ticket, **extra) -> dict:
    """What the two emails about one enquiry say about it.

    Whether anybody has it is worked out here and handed over as a finished
    sentence and a finished line, rather than left to an {% if %} in the
    template. System Emails pre-fills its editor from the template with each
    tag standing in for its value, an {% if %} on a tag is always true there,
    and so the "nobody has it yet" wording would be missing from anything
    saved from the editor.
    """
    assignee = ticket.assignee
    return _context(
        ticket,
        ASSIGNEE_LINE=f"Assigned to {_name(assignee)}" if assignee else "Unassigned",
        ASSIGNMENT=(
            f"It is assigned to {_name(assignee)}."
            if assignee
            else "It is not assigned to anyone yet."
        ),
        CATEGORY_LABEL=TicketCategory(ticket.category).label,
        PRIORITY_LABEL=TicketPriority(ticket.priority).label,
        CTA_URL=_support_queue_url(ticket),
        **extra,
    )


def send_new_ticket_to_support(ticket) -> bool:
    """E4. Sent to the support inbox when someone raises an enquiry (C-17).

    The designer's M-27: who raised it, its category and urgency, whether
    anyone has it yet, and a button straight to it in the queue. Not the
    message itself. The requesters are school students, what they write can
    hold anything about them, and a copy sitting in a shared mailbox is a copy
    outside the platform's own access rules; the button is one click from it.

    Only for enquiries raised in the portal. Message screening's tickets send
    E6 instead (send_flagged_message_to_support).
    """
    if _fresh(ticket, "ticket_new_for_support") is None:
        return False
    requester = ticket.created_by
    ctx = _support_ticket_context(
        ticket,
        REQUESTER_NAME=_name(requester) if requester else "Someone",
        URGENCY_WORDS=URGENCY_WORDS.get(ticket.priority, ""),
    )
    return _send_to_support(
        "ticket_new_for_support",
        ctx,
        text_body=(
            "Hi support team,\n\n"
            "A new enquiry has come in: {TICKET_NUMBER}.\n\n"
            "Raised by: {REQUESTER_NAME}, in the Support Centre\n"
            "Category: {CATEGORY_LABEL}\n"
            "Urgency: {URGENCY_WORDS} ({PRIORITY_LABEL} priority)\n"
            "{ASSIGNEE_LINE}\n"
            "Subject: {TICKET_SUBJECT}\n\n"
            "Open it in the support queue: {CTA_URL}\n\n"
            "This is an automatic message from {BRAND_CONNECT}.\n"
        ),
    ) == SENT


def send_flagged_message_to_support(ticket) -> bool:
    """E6. Sent to the support inbox when the AI screening flags a chat
    message and opens an enquiry for it.

    The client, on 20 October: "Please do cause an email to be triggered from
    the AI screening flags as well". handoff.create_ticket_from_screening
    calls it once the screening batch commits, so a batch that rolls back
    mails nobody.

    E4's layout with the screener in place of a requester, and, for E4's
    reason and more, not the message: a flagged chat message and who wrote it
    are a child's own words, and they stay in the enquiry, behind the queue's
    access rules. The subject the hand-off writes names the kind of message
    and the group, so the inbox can tell one flag from another.
    """
    if _fresh(ticket, "ticket_flagged_for_support") is None:
        return False
    ctx = _support_ticket_context(ticket)
    return _send_to_support(
        "ticket_flagged_for_support",
        ctx,
        text_body=(
            "Hi support team,\n\n"
            "A chat message was flagged: {TICKET_NUMBER}.\n\n"
            "The AI screening flagged a message in a group chat and opened an enquiry "
            "for it. {ASSIGNMENT}\n"
            "Category: {CATEGORY_LABEL}\n"
            "Priority: {PRIORITY_LABEL}\n"
            "Subject: {TICKET_SUBJECT}\n\n"
            "The message itself is not in this email. It is in the enquiry, with who "
            "sent it and why it was flagged.\n\n"
            "Open it in the support queue: {CTA_URL}\n\n"
            "This is an automatic message from {BRAND_CONNECT}.\n"
        ),
    ) == SENT


def _sydney_date(now) -> str:
    """"Friday 9 October 2026": the morning it lands in, where the team is."""
    from zoneinfo import ZoneInfo

    local = now.astimezone(ZoneInfo("Australia/Sydney"))
    return f"{local:%A} {local.day} {local:%B %Y}"


def send_open_tickets_digest(now=None) -> dict:
    """E5. The morning count of enquiries still open, to the support inbox.

    The client asked for "maybe like a daily digest or something, where you
    have like 'this is the number of inquiries open'" (C-18), and on 20
    October said when: "9am Sydney time" and "Daily everyday (weekends
    included)". The time is the schedule's (.github/workflows/ticket-digest.yml);
    this sends whenever it is called.

    It goes on a morning with nothing open as well, with zeros in it. It used
    to be skipped then, so that a daily "0 open" would not become mail
    somebody learns to ignore; Jinqi settled on 21 October that it goes every
    day ("没有也要发"), which is how "daily everyday" reads too.

    The designer's M-28 lays it out: open, in progress, pending user, and how
    many of those are overdue, which is the queue's own Overdue rule
    (services/queue.overdue_condition). Each row is its own number in the
    template rather than a loop, so wording saved on System Emails keeps the
    table. Counted when it is sent, not stored, so a run that comes late or
    twice says what is true at that moment.
    """
    from django.db.models import Count, Q
    from django.utils import timezone

    from .queue import live_tickets, overdue_condition

    now = now or timezone.now()
    still_open = live_tickets().exclude(status=TicketStatus.RESOLVED)
    counts = still_open.aggregate(
        total=Count("pk"),
        overdue=Count("pk", filter=overdue_condition(now)),
        open=Count("pk", filter=Q(status=TicketStatus.OPEN)),
        in_progress=Count("pk", filter=Q(status=TicketStatus.IN_PROGRESS)),
        pending_user=Count("pk", filter=Q(status=TicketStatus.PENDING_USER)),
    )
    total = counts["total"]
    if total == 0:
        headline = "No enquiries are open"
    else:
        headline = f"{total} enquir{'y is' if total == 1 else 'ies are'} still open"
    ctx = {
        **brand_context(),
        "OPEN_TOTAL": total,
        "HEADLINE": headline,
        "TODAY": _sydney_date(now),
        "OPEN_COUNT": counts["open"],
        "IN_PROGRESS_COUNT": counts["in_progress"],
        "PENDING_USER_COUNT": counts["pending_user"],
        "OVERDUE": counts["overdue"],
        "CTA_URL": _support_queue_url(),
    }
    result = _send_to_support(
        "ticket_digest",
        ctx,
        text_body=(
            "Hi support team,\n\n"
            "{HEADLINE}. Here is where the support queue stands this morning, {TODAY}.\n\n"
            "Open: {OPEN_COUNT} (Nobody has picked it up yet)\n"
            "In progress: {IN_PROGRESS_COUNT} (Someone is working on it)\n"
            "Pending user: {PENDING_USER_COUNT} (Waiting on the requester)\n"
            "Of these, overdue: {OVERDUE} (longer than its priority allows)\n\n"
            "We send this summary every morning, weekends included.\n\n"
            "Open the support queue: {CTA_URL}\n\n"
            "This is an automatic message from {BRAND_CONNECT}.\n"
        ),
    )
    outcome = {"sent": result == SENT, "open": total, "overdue": counts["overdue"]}
    if result == SKIPPED:
        outcome["reason"] = "switched_off"
    return outcome
