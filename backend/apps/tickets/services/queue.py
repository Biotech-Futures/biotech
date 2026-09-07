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
from rest_framework import serializers

from ..models import (
    OFF_THE_CLOCK_STATUSES,
    Ticket,
    TicketPriority,
    TicketStatus,
)

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
    """The ball is with support, and has been for longer than it should be.

    The client wrote the rule out for us on 2026-09-04, after rejecting a
    first-response-only test:

        Raised
        Responded to and if not closed
        Responded to by the ticket owner
        If a support agent hasn't then responded to it after 4 hours it
        should be marked as overdue

    So the clock runs whenever it is our move, restarts every time the
    requester answers, and stops every time we do. The old rule read
    ``first_response_at IS NULL``, which meant a single reply made a ticket
    permanently safe however long it then sat — the exact behaviour the client
    replaced. ``first_response_at`` is still written and is still what the p52
    "time to first response" figure is computed from; it just no longer
    decides this.

    Still worked out on the spot rather than stored. What is stored is when
    the clock started (``Ticket.awaiting_support_since``, maintained by
    services/lifecycle), never the verdict — a stored verdict would need a
    scheduled job to flip it and would be wrong between runs, while a stored
    start time compared against ``now`` here cannot go stale.

    The deadline follows the ticket's *current* priority, and priority is a
    field support can correct. Re-triaging therefore moves the deadline, so a
    badge can appear or disappear on a ticket nobody has answered. That is
    what the client's two 2026-09-04 rules come to when both are held: the
    bands are per priority, and the agent may change a priority the requester
    chose. The anchor is left alone on a priority change, which is the safe
    half of it. Re-arming the clock there would let an agent zero it with two
    clicks on a dropdown, and an overdue count anybody can reset is not a
    count.

    Two independent guards keep a "pending user" ticket out, and that is
    deliberate rather than an accident:

      * the anchor is null, because every path into "pending user" clears it;
      * and the status is excluded outright.

    Delete either one and the other still holds, so a mutation test that
    removes one guard will not go red. That is the nature of redundant
    defence, and it is here because the two mechanisms fail differently: the
    anchor could be left stale by a backfill or by a future write path that
    forgets it, and the status could be corrected by hand to something the
    anchor was never updated for. Anyone tempted to remove one should delete
    both, watch the tests go red, and then put both back.
    """
    now = now or timezone.now()
    past_deadline = Q()
    for priority, hours in _sla_hours().items():
        past_deadline |= Q(
            priority=priority,
            awaiting_support_since__lt=now - timedelta(hours=hours),
        )
    return (
        ~Q(status__in=OFF_THE_CLOCK_STATUSES)
        & Q(awaiting_support_since__isnull=False)
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

# Same trick for "nobody owns this one". The summary card counts these, so
# without a filter value the card was a number you could not click through to.
# Intercepted before the int() below, which is why that coercion was kept here
# rather than pushed into a serializer.
UNASSIGNED = "__unassigned__"


def database_id(raw, name):
    """A query-string value read as a row id, or a 400.

    Two separate things, and the second is the one that bites. A non-number
    has to be refused because Django coerces at query-build time and raises
    ValueError, which the platform's handler turns into a 500 rather than a
    400.

    And a digits-only value past 2^63 sails through int() and then overflows:
    SQLite raises OverflowError — a 500 for a number somebody typed into the
    query string — while PostgreSQL shrugs and matches nothing. The tests run
    on SQLite and production runs on PostgreSQL, so the two disagree about the
    same request, and CI is the strict one. No real id can be out there, so
    the answer is the same 400 as for a non-number.

    Shared rather than repeated: the audit endpoint grew its own copy of the
    first half and not the second, so ?actor= with a huge number answered 200
    on PostgreSQL and 500 on SQLite while ?assignee= answered 400 on both.
    """
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise serializers.ValidationError(
            {name: f"{name} must be an integer."}
        ) from exc
    if not (-(2 ** 63) <= value < 2 ** 63):
        raise serializers.ValidationError({name: f"{name} must be an integer."})
    return value


def apply_filters(queryset, *, region=None, status=None, category=None,
                  assignee=None, priority=None, search=None):
    if region:
        queryset = queryset.filter(region="" if region == UNKNOWN_REGION else region)
    if status:
        queryset = queryset.filter(status=status)
    if category:
        queryset = queryset.filter(category=category)
    if assignee == UNASSIGNED:
        queryset = queryset.filter(assignee__isnull=True)
        # Resolved is excluded as well. The sentinel exists so the summary
        # card can be clicked through; summary() counts unowned tickets that
        # are not resolved, so without the same exclusion here a card reading
        # 3 opens a list of 5.
        #
        # Lifted for exactly two filters, and the pair is not "any other
        # filter". Applied as a flat rule the exclusion went on to hide rows
        # the agent had asked for by name: choosing Resolved in the status
        # dropdown beside it emptied the table, and searching an unowned
        # resolved ticket by its own number answered "No tickets match these
        # filters" about a ticket that is right there in the database. Both
        # are the queue asserting something untrue about its own contents.
        #
        # Region, category and priority are the other direction. None of
        # them names a resolved ticket. They narrow the pile; they do not ask
        # for anything outside it. And the card carries whatever is already on
        # screen when it is clicked, because TicketQueuePage spreads the
        # current filters into the link on purpose so a region the agent had
        # chosen is not silently dropped. Letting those three lift the
        # exclusion put the original mismatch straight back on the card's own
        # path: a card reading 1 opening a list of 2, with the extra row
        # resolved.
        if not (status or search):
            queryset = queryset.exclude(status=TicketStatus.RESOLVED)
    elif assignee:
        # The only filter that is not a string column. On a CharField any
        # value is legal and simply matches nothing; on an FK id Django
        # coerces at query-build time, and a non-number raises ValueError,
        # which the platform's handler turns into a 500 rather than a 400.
        queryset = queryset.filter(assignee_id=database_id(assignee, "assignee"))
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
    """Everyone who can be assigned a ticket: agents and admins, deduplicated.

    Active accounts only. Deactivating someone does not delete their support
    or admin scope row — the two are independent on this platform — so
    without this an agent who left in March stays in the assignee dropdown,
    and a ticket handed to them leaves both the Unassigned and the Open
    counters while nobody is actually working it.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.filter(
        Q(support_scope__isnull=False) | Q(adminscope__isnull=False),
        is_active=True,
    ).distinct().order_by("first_name", "last_name", "id")


def assignee_filter_options():
    """Who can appear in the queue's *assignee filter*.

    Wider than who can be assigned, and deliberately so. Deactivating an agent
    does not move the tickets already in their name, so filtering by them is
    the only way to find that work in bulk — and dropping them from this list
    would make thirty in-progress tickets invisible while nobody is working
    them. Assignment itself stays restricted to active accounts.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    # Worked out separately rather than as another OR'd join condition:
    # `tickets_assigned__deleted_at__isnull=True` also matches every user with
    # no tickets at all, because the outer join hands back NULL for them.
    owners = (
        live_tickets()
        .exclude(assignee__isnull=True)
        .values_list("assignee_id", flat=True)
        .distinct()
    )
    return User.objects.filter(
        Q(support_scope__isnull=False)
        | Q(adminscope__isnull=False)
        | Q(pk__in=owners)
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
