from django.db import models
from django.utils import timezone


class TicketAttachment(models.Model):
    """A file hanging off one timeline message.

    Visibility follows the parent message (D6): an attachment on an internal
    note does not exist as far as the requester is concerned. Because the id
    is a plain auto-increment and therefore guessable, every requester-facing
    attachment query has to carry that exclusion as a queryset condition.
    """

    message = models.ForeignKey(
        "tickets.TicketMessage",
        on_delete=models.CASCADE,
        related_name="attachments",
        db_index=True,
    )
    storage_key = models.CharField(max_length=512)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'ticket_attachments'
        verbose_name = "Ticket Attachment"
        verbose_name_plural = "Ticket Attachments"

    def __str__(self):
        return f"{self.original_filename} ({self.size} bytes)"
