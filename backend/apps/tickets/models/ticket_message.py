from django.conf import settings
from django.db import models
from django.utils import timezone


class TicketMessageType(models.TextChoices):
    USER_MESSAGE = "user_message", "User message"
    SUPPORT_REPLY = "support_reply", "Support reply"
    # Never leaves the support side. Stripped at the queryset layer on every
    # requester-facing endpoint (D6), not hidden by the frontend.
    INTERNAL_NOTE = "internal_note", "Internal note"
    SYSTEM = "system", "System message"


class TicketMessage(models.Model):
    """One row on a ticket's timeline — the ledger the requester reads.

    The second ledger is ``audit.AuditLog`` (DEC-002), which records the same
    events for the support side with before/after snapshots.
    """

    ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    # Null for system messages; ``message_type`` is what distinguishes them,
    # never a null author.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="ticket_messages",
    )
    message_type = models.CharField(
        max_length=20,
        choices=TicketMessageType.choices,
    )
    body = models.TextField()
    # default=timezone.now, not auto_now_add (DEC-014⑤): tests need to be able
    # to place a message at an arbitrary point in the past.
    created_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'ticket_messages'
        verbose_name = "Ticket Message"
        verbose_name_plural = "Ticket Messages"
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
        ]

    def __str__(self):
        return f"{self.ticket_id} / {self.message_type} @ {self.created_at}"
