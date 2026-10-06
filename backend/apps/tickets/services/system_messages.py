"""The exact wording of every system message the timeline can carry.

Collected in one module on purpose: these are the only sentences on the
ticket that nobody signs, so they are the ones most likely to drift into
saying something the platform cannot guarantee. Changing one is a wording
decision, not an implementation detail.

Source of truth: .capstone/design/ticketing/05-conversation-model.md §2.
"""

from ..models import TicketStatus

# No line for T1 (a new ticket) or T3 (the first pick-up from the pool). There
# used to be one for each: "Thanks {first_name}. We're looking into this and
# will get back to you shortly." and "Your ticket is now being handled." The
# client asked for both to go (C-05): "I don't think that adds anything." The
# receipt email already says the first, and the status badge moving from Open
# to In progress already says the second. Tickets raised before the change
# still carry the old rows. They are history and are left alone, and nothing
# in the code reads them back.

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


def status_changed(new_status: str) -> str:
    return STATUS_CHANGED.format(label=TicketStatus(new_status).label)


def email_delivery_failed(recipient: str) -> str:
    return EMAIL_DELIVERY_FAILED.format(recipient=recipient)
