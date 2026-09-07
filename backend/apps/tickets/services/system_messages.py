"""The exact wording of every system message the timeline can carry.

Collected in one module on purpose: these are the only sentences on the
ticket that nobody signs, so they are the ones most likely to drift into
saying something the platform cannot guarantee. Changing one is a wording
decision, not an implementation detail.

Source of truth: .capstone/design/ticketing/05-conversation-model.md §2.
"""

from ..models import TicketStatus

# T1 — dropped into the timeline the moment the ticket is created, rather
# than "within ~2 minutes" as the client's mock-up suggested.
AUTO_ACKNOWLEDGEMENT = "Thanks {first_name}. We're looking into this and will get back to you shortly."
AUTO_ACKNOWLEDGEMENT_NO_NAME = "Thanks. We're looking into this and will get back to you shortly."

# T3 — deliberately says only what changed, never who picked it up. Naming
# the agent in a requester-visible message is what DEC-017 was written to
# prevent.
TICKET_NOW_HANDLED = "Your ticket is now being handled."

# T4 — written by add_support_reply(move_to_pending=True), which is the reply
# that asks the question, and by mark_pending(), which production does not
# call. Either way a real reply sits directly above it on the timeline.
#
# Two sentences rather than a dash parenthetical: the team's standing style
# note is that these read better split, and this line only started reaching
# requesters when the combined action landed.
MOVED_TO_PENDING_USER = "We've asked for more information. See the reply above."

# T6
RESOLVED = (
    "This ticket has been marked as resolved. "
    "Reply here if you need further help and it will reopen automatically."
)

# T7
REOPENED = "Ticket reopened following your reply. Our team will take another look."

# DEC-012 — written by the mail worker when a resolution email bounces, so an
# agent can see it and follow up by hand.
EMAIL_DELIVERY_FAILED = (
    "Resolution email to {recipient} could not be delivered. Please follow up."
)

# T8 — a status corrected from the dropdown, with no reply attached. The
# design gives no wording for these landings; deliberately neutral, because
# the T4 sentence above points at "the reply above" and there isn't one.
STATUS_CHANGED = "Status changed to {label}."


def auto_acknowledgement(first_name: str) -> str:
    first_name = (first_name or "").strip()
    if not first_name:
        return AUTO_ACKNOWLEDGEMENT_NO_NAME
    return AUTO_ACKNOWLEDGEMENT.format(first_name=first_name)


def status_changed(new_status: str) -> str:
    return STATUS_CHANGED.format(label=TicketStatus(new_status).label)


def email_delivery_failed(recipient: str) -> str:
    return EMAIL_DELIVERY_FAILED.format(recipient=recipient)
