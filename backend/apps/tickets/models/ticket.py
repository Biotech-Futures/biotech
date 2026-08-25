from django.conf import settings
from django.db import models
from django.utils import timezone


class TicketCategory(models.TextChoices):
    """The three self-serve topics the client specified (p48 R48-5).

    Hard-coded to three for the first version; the choices list is the single
    place to extend from (D10/U4).
    """

    ACCOUNT_ACCESS = "account_access", "Account & Access"
    PROGRAMS_GROUPS = "programs_groups", "Programs & Groups"
    CERTIFICATES_RECORDS = "certificates_records", "Certificates & Records"


class TicketStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In progress"
    PENDING_USER = "pending_user", "Pending user"
    RESOLVED = "resolved", "Resolved"


class TicketPriority(models.TextChoices):
    HIGH = "high", "High"
    NORMAL = "normal", "Normal"
    LOW = "low", "Low"


class TicketChannel(models.TextChoices):
    PORTAL = "portal", "Portal"
    # Reserved, deliberately not activated in the first version: the email
    # channel (inbound creation and reply threading) is a later goal, so no
    # code path writes this value yet.
    EMAIL = "email", "Email"
    AI_SCREENING = "ai_screening", "AI screening"


class Ticket(models.Model):
    """A support enquiry. Contact -> Route -> Own -> Converse -> Resolve.

    Two update clocks, deliberately (DEC-002/D1):

    ``updated_at``        what the requester sees as "last updated". Only
                          user-visible events move it.
    ``support_updated_at`` the support queue's sort key. Every event moves it,
                          including internal notes, assignment hand-offs and
                          priority changes.

    Both are ``default=timezone.now`` rather than ``auto_now`` (DEC-016①):
    ``auto_now`` stamps on every ``save()``, which would let a priority change
    bump the requester's clock and float the ticket with nothing to show for
    it in the timeline. All writes go through
    ``apps.tickets.services.lifecycle._touch``.
    """

    ticket_number = models.CharField(max_length=16, unique=True, db_index=True)
    subject = models.CharField(max_length=255)
    # No max_length here on purpose (DEC-019 A2): the 2000-character cap is a
    # serializer concern. TextField(max_length=...) would bake the cap into
    # 0001_initial and force an AlterField the moment it is tuned.
    body = models.TextField()
    category = models.CharField(
        max_length=32,
        choices=TicketCategory.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        max_length=10,
        choices=TicketPriority.choices,
        default=TicketPriority.NORMAL,
        db_index=True,
    )
    # Snapshot of the requester's country taken at submission (DEC-006), not a
    # live join: the queue must keep filtering correctly after a user edits
    # their profile or is deleted. Width matches the source column
    # Countries.country_name(255) so the snapshot can never truncate.
    region = models.CharField(max_length=255, blank=True, db_index=True)
    channel = models.CharField(
        max_length=20,
        choices=TicketChannel.choices,
        default=TicketChannel.PORTAL,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="tickets_created",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        db_index=True,
        related_name="tickets_assigned",
    )
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    support_updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    # No db_index (DEC-019 A1): all six existing soft-delete columns on the
    # platform go without one, and the column is null for almost every row.
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'tickets'
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"

    def __str__(self):
        return f"{self.ticket_number} ({self.status})"
