"""Queries behind the support queue: filtering, searching, and the counters.

The overdue rule is written once, as a queryset condition, and used both to
count the card and to mark rows. A second copy in Python would be one
refactor away from disagreeing with the first, and "the card says four but I
can only find three" is a bug nobody enjoys.
"""

from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from ..models import Ticket, TicketPriority, TicketStatus

# The queue never shows soft-deleted tickets: deleting one is how an agent
# fixes a mistake, so it must disappear from the queue, the search and any
# bulk action.
def live_tickets():
    return Ticket.objects.filter(deleted_at__isnull=True)


def _sla_hours():
    return {
        TicketPriority.HIGH: settings.TICKET_SLA_HIGH_HOURS,
        TicketPriority.NORMAL: settings.TICKET_SLA_NORMAL_HOURS,
        TicketPriority.LOW: settings.TICKET_SLA_LOW_HOURS,
    }


def overdue_condition(now=None) -> Q:
    """Not resolved, never answered, and past its deadline.

    Overdue is worked out on the spot rather than stored. Storing it would
    mean a scheduled job to flip the flag, and a ticket whose badge is wrong
    until that job next runs.
    """
    now = now or timezone.now()
    past_deadline = Q()
    for priority, hours in _sla_hours().items():
        past_deadline |= Q(priority=priority, created_at__lt=now - timedelta(hours=hours))
    return (
        ~Q(status=TicketStatus.RESOLVED)
        & Q(first_response_at__isnull=True)
        & past_deadline
    )


def overdue_ids(tickets, now=None) -> set:
    """Which of these tickets are overdue, in one query."""
    ids = [t.pk for t in tickets]
    if not ids:
        return set()
    return set(
        live_tickets()
        .filter(overdue_condition(now), pk__in=ids)
        .values_list("pk", flat=True)
    )


# Region is stored as a snapshot string and is empty when we never knew the
# requester's country. That empty bucket is shown as "Unknown", so it needs a
# value the filter can actually carry — an empty query parameter reads as
# "no filter" everywhere else on the platform.
UNKNOWN_REGION = "__unknown__"


def apply_filters(queryset, *, region=None, status=None, category=None,
                  assignee=None, priority=None, search=None):
    if region:
        queryset = queryset.filter(region="" if region == UNKNOWN_REGION else region)
    if status:
        queryset = queryset.filter(status=status)
    if category:
        queryset = queryset.filter(category=category)
    if assignee:
        queryset = queryset.filter(assignee_id=assignee)
    if priority:
        queryset = queryset.filter(priority=priority)
    if search:
        queryset = queryset.filter(
            Q(ticket_number__icontains=search)
            | Q(subject__icontains=search)
            | Q(created_by__first_name__icontains=search)
            | Q(created_by__last_name__icontains=search)
            | Q(created_by__email__icontains=search)
        )
    return queryset


def summary(now=None) -> dict:
    now = now or timezone.now()
    base = live_tickets()
    return {
        "unassigned": base.filter(assignee__isnull=True)
                          .exclude(status=TicketStatus.RESOLVED).count(),
        "open": base.filter(status=TicketStatus.OPEN).count(),
        "pendingUser": base.filter(status=TicketStatus.PENDING_USER).count(),
        "overdue": base.filter(overdue_condition(now)).count(),
    }


def support_capable_users():
    """Everyone who can be assigned a ticket: agents and admins, deduplicated."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.filter(
        Q(support_scope__isnull=False) | Q(adminscope__isnull=False)
    ).distinct().order_by("first_name", "last_name", "id")


def known_regions():
    """Distinct regions in use, with the Unknown bucket pinned to the end."""
    values = (
        live_tickets()
        .exclude(region="")
        .values_list("region", flat=True)
        .distinct()
        .order_by("region")
    )
    return [{"value": region, "label": region} for region in values] + [
        {"value": UNKNOWN_REGION, "label": "Unknown"}
    ]
