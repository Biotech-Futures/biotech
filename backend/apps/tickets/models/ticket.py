from django.conf import settings
from django.db import models
from django.utils import timezone


class TicketCategory(models.TextChoices):
    """The eight self-serve topics the client specified, plus one the platform
    fills in for itself.

    The list is the client's own, given on 2026-09-04 in answer to our
    question "is Account & Access / Programs & Groups / Certificates & Records
    the full list?". It is not: those three were our guess, and the client's
    reply was "that was just an AI byproduct haha, please set the below as
    categories". So the eight below are quoted from them, in their order.

    Two things about the wording are deliberate and should not be tidied.
    "General Question" is title case while the other seven are sentence case;
    that is how the client wrote it, and it is their vocabulary to set. And
    the two survivors from the old list keep their database values
    (``account_access``, ``certificates_records``) even though their labels
    changed from "&" to "and" — the value is an internal key and the label is
    the only part anyone reads, exactly as ``in_progress`` renders as
    "In progress".

    ``programs_groups`` is gone. It has no home in the client's list, and
    migration 0005 rewrites the rows that carried it to ``other`` rather than
    to ``general_question``: "Other" is honestly the bucket for "we no longer
    have a name for this", while "General Question" is a bucket the client
    will read as meaningful on the p52 breakdown.

    FLAGGED_CONTENT is not offered to requesters: the submission serializer
    accepts only PUBLIC_TICKET_CATEGORIES (serializers.py), which is spelled
    out separately for exactly this reason, and the portal's dropdown is built
    from the same list. It exists because message screening has to file its
    tickets under something, and every requester-facing topic is a subject a
    person chose for themselves. A child-safety flag is none of those, and
    filing it under one would corrupt the category breakdown on p52, the one
    place the client asked to see what people are asking about.
    """

    ACCOUNT_ACCESS = "account_access", "Account and access"
    REGISTRATION = "registration", "Registration"
    HELP_STUDENT_GROUP = "help_student_group", "Help with a student or group"
    HELP_MENTOR = "help_mentor", "Help with a mentor"
    TECHNICAL_ISSUE = "technical_issue", "Technical issue"
    CERTIFICATES_RECORDS = "certificates_records", "Certificates and records"
    GENERAL_QUESTION = "general_question", "General Question"
    OTHER = "other", "Other"
    FLAGGED_CONTENT = "flagged_content", "Flagged content"


class TicketStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In progress"
    PENDING_USER = "pending_user", "Pending user"
    RESOLVED = "resolved", "Resolved"


class TicketPriority(models.TextChoices):
    HIGH = "high", "High"
    NORMAL = "normal", "Normal"
    LOW = "low", "Low"


# The two states in which support is not waiting on anything, so the Overdue
# clock does not run.
#
# It lives beside the choices rather than in a service because both sides of
# the module read it and they read it in opposite directions: lifecycle stops
# the clock on entering one of these and starts it on leaving, while
# queue.overdue_condition excludes them from the badge. Writing either
# direction out longhand is how the two came apart twice — first by re-arming
# on every non-pending status change, then by missing the way back out of
# "resolved".
OFF_THE_CLOCK_STATUSES = (TicketStatus.PENDING_USER, TicketStatus.RESOLVED)


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
    # The requester's role, frozen the same way and for the same reason: the
    # dashboard segments by user type, and a live join through
    # RoleAssignmentHistory would re-label a year of history the day somebody
    # is promoted, and lose it entirely when an account is deleted
    # (created_by is SET_NULL). Blank means we never knew — including every
    # ticket raised before this column existed.
    requester_role = models.CharField(max_length=255, blank=True, db_index=True)
    channel = models.CharField(
        max_length=20,
        choices=TicketChannel.choices,
        default=TicketChannel.PORTAL,
        db_index=True,
    )
    # PROTECT, not SET_NULL, and it is a deliberate correction.
    #
    # A ticket body is free text a minor wrote about a problem they were
    # having: "I am being bullied in my group chat", an address, a phone
    # number, a parent's email. The platform already has a rule for that kind
    # of content — chat.Messages.sender_user is PROTECT, so deleting an
    # account that has ever written a message is refused, and an admin who
    # means it passes force=True, which purges the messages first
    # (apps/admin/services/user.py). Tickets were SET_NULL, so deleting a
    # student succeeded and left every word they had written sitting in the
    # support queue under no name at all. The docstring on delete_user says
    # "Delete a user and all related data"; for tickets it was not true.
    #
    # Nullable still, because a ticket raised by message screening has no
    # requester at all. Null is "there was never a person here", not "there
    # was one and they are gone" — which is also what makes the queue's
    # `anonymous` flag honest again.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.PROTECT,
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
    # When the ball last landed with support, or null when it is not with
    # support at all. This is the clock the Overdue badge is measured from.
    #
    # It exists because the client rejected a first-response-only rule. Asked
    # on 2026-09-04 whether "no first reply within 4 / 24 / 72 hours" was the
    # right test, they answered: "instead of making it just the first
    # response, include follow up responses", and spelled out the loop —
    # raised, responded to, responded to by the person who raised it, and if
    # support has not answered again within the window it is overdue. The old
    # rule read ``first_response_at IS NULL``, so one reply made a ticket
    # permanently safe however long it then sat.
    #
    # A timestamp and deliberately not a boolean. Storing "is overdue" would
    # need a scheduled job to flip it and would be wrong between runs; storing
    # when the clock started needs no job at all, because the comparison
    # against the deadline still happens at read time
    # (services/queue.overdue_condition).
    #
    # Maintained by the lifecycle service, which is the only thing that writes
    # to tickets. Set on submission, on a requester's reply, on reopen, and
    # when an agent moves a ticket back off "pending user". Cleared by a
    # support reply, by "pending user", and by resolving. Deliberately NOT
    # touched by claiming, assigning or writing an internal note: none of
    # those is an answer, so none of them should make the red number go down.
    #
    # Indexed because it is a predicate on the queue's main list query.
    awaiting_support_since = models.DateTimeField(null=True, blank=True, db_index=True)
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
