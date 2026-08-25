from django.db import transaction
from django.utils import timezone

from ..models import TicketCounter


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
    with transaction.atomic():
        row, _ = TicketCounter.objects.select_for_update().get_or_create(year=year)
        row.last_number += 1
        row.save(update_fields=["last_number"])
        return f"SUP-{year}-{row.last_number:05d}"
