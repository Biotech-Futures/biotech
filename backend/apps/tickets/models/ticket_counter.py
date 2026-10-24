from django.db import models


class TicketCounter(models.Model):
    """One row per calendar year, holding the last ticket number issued.

    Singular ``db_table`` follows the platform convention for single/few-row
    tables. Allocation takes a row lock; see
    :func:`apps.tickets.services.numbering.allocate_ticket_number`.
    """

    year = models.SmallIntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    class Meta:
        db_table = 'ticket_counter'
        verbose_name = "Ticket Counter"
        verbose_name_plural = "Ticket Counters"

    def __str__(self):
        return f"{self.year} -> {self.last_number}"
