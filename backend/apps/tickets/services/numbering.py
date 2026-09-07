from django.db import transaction
from django.utils import timezone

from ..models import Ticket, TicketCounter


def allocate_ticket_number() -> str:
    """Hand out the next ``SUP-<year>-<00001>`` number.

    The row lock closes the read-then-write gap that would otherwise let two
    concurrent submissions read the same counter value (DEC-007); the unique
    constraint on ``Ticket.ticket_number`` is the backstop. Callers are
    expected to run this inside the same transaction that inserts the ticket,
    so a failed submission rolls the counter back instead of burning a number.

    The year is read in UTC (DEC-019 B1) because the platform runs on
    ``TIME_ZONE = "UTC"``. Reading it in local time would open an 11-hour
    window each new year where two callers disagree about which counter row
    they are incrementing.

    ``timezone`` is imported into this module on purpose: the tests stub
    ``apps.tickets.services.numbering.timezone.now`` to cross a year boundary,
    and neither ``freezegun`` nor ``time-machine`` is a dependency here.
    """
    year = timezone.now().year
    prefix = f"SUP-{year}-"
    with transaction.atomic():
        row, _ = TicketCounter.objects.select_for_update().get_or_create(year=year)
        row.last_number += 1
        # The counter cannot drift on its own, but nothing outside this
        # function is obliged to keep it honest: a partial restore, or a row
        # inserted by hand, leaves numbers in the table this row never handed
        # out. Land on one of those and the insert fails on the unique
        # constraint, the number rolls back with the transaction as it is
        # meant to, and the next submission takes the same number and fails
        # the same way. Nothing recovers from that inside the year. The queue
        # simply stops accepting tickets until somebody edits the database.
        #
        # So step over what is already there. One indexed lookup on the
        # ordinary path, where nothing is in the way.
        #
        # ``max`` rather than a plain assignment, because the jump has to be
        # forwards. The whole premise here is a table somebody edited by
        # hand, and a number edited by hand is the one most likely not to
        # parse. _highest_in_use answers 0 for one of those, and a bare
        # assignment on that answer would wind the counter back to 1 and
        # start handing out numbers that are already taken.
        if Ticket.objects.filter(
            ticket_number=f"{prefix}{row.last_number:05d}"
        ).exists():
            row.last_number = max(row.last_number, _highest_in_use(prefix) + 1)
        row.save(update_fields=["last_number"])
        return f"{prefix}{row.last_number:05d}"


def _highest_in_use(prefix: str) -> int:
    """The largest number a ticket of this year already carries.

    Jumped to in one step rather than counted up to. A restore can leave
    hundreds of consecutive numbers in the way, and stepping over them one at
    a time would be one query each while the counter row is locked.

    Fixed-width padding is what makes the string order the numeric order, so
    the largest number is simply the last string. That holds for as long as
    the numbers fit the five digits the format pads to, which is two orders of
    magnitude above anything this platform will issue in a year; past that the
    unique constraint is still the backstop it was before.

    Soft-deleted tickets count. The row is still there and so is its hold on
    the constraint, which is why deleting the ticket in the way is not a way
    out of this.

    A number that does not parse counts as 0, so a table where nothing is
    readable answers 0 rather than raising. The caller never lowers the
    counter on that answer.
    """
    last = (
        Ticket.objects.filter(ticket_number__startswith=prefix)
        .order_by("-ticket_number")
        .values_list("ticket_number", flat=True)
        .first()
    )
    tail = (last or "").removeprefix(prefix)
    return int(tail) if tail.isdigit() else 0
