"""The numbers behind the ticket dashboard (client PPT p52).

Four groups of measures, each answering the question the client wrote above
it, plus segmentation. Everything is computed on the spot from columns that
already exist — there is no reporting table to keep in step, and at this
platform's scale (hundreds of tickets a year, not millions) an aggregate query
per measure costs nothing.

Two things worth knowing before reading a number off this:

* Date boundaries are UTC, matching the ticket numbering (DEC-019). A ticket
  raised at 09:00 Sydney time on 1 March lands in February for a viewer who
  filters "February", which is surprising until you know the rule and
  unexplainable if you do not.

* "Age by status" is time since the last support-side activity, not total time
  spent in that status. Reconstructing the latter needs a state-transition
  history the platform does not keep. This is what the client's "where does
  work slow down?" question actually needs — a ticket sitting untouched for
  nine days is the signal, whether or not it changed status on day one.
"""

from datetime import timedelta

from django.db.models import Avg, Count, F, Q
from django.utils import timezone

from ..models import Ticket, TicketStatus
from .queue import live_tickets, overdue_condition

# Which column each segment name reads. Region is first because the client's
# own screenshot has it selected — it is the dimension they think in.
#
# "Program stage" is in the client's list and is deliberately absent here: the
# platform has no such field, and inventing one would put a made-up number in
# front of them. Raise it when the dashboard is demonstrated.
SEGMENTS = {
    "region": "region",
    "userType": "requester_role",
    "category": "category",
    "status": "status",
    "assignee": "assignee_id",
    "channel": "channel",
    # Added 2026-09-04 with the requester-chosen priority. Before that every
    # portal ticket was Normal and this would have been a chart with one bar;
    # now that people declare their own urgency, "how many High did we get" is
    # the first question the numbers can answer.
    "priority": "priority",
}


def _seconds(value):
    """Averages come back as timedelta; JSON does not carry those."""
    if value is None:
        return None
    if isinstance(value, timedelta):
        return round(value.total_seconds())
    # Some backends hand back a raw number of seconds for a duration average.
    return round(float(value))


def _in_window(queryset, start, end):
    if start:
        queryset = queryset.filter(created_at__gte=start)
    if end:
        queryset = queryset.filter(created_at__lt=end)
    return queryset


def _counts_by(queryset, column):
    """[{value, count}], commonest first, so a chart needs no further sorting."""
    rows = (
        queryset.values(column)
        .annotate(count=Count("id"))
        .order_by("-count", column)
    )
    return [
        # Always a string. None only reaches here for assignee, rendered as
        # the empty string so the front end has one "no value" case rather
        # than two; and assignee_id is an integer, which the client's schema
        # declares as a string — an owned ticket in the window used to fail
        # the parse and blank the entire dashboard, not just this chart.
        {
            "value": "" if row[column] is None else str(row[column]),
            "count": row["count"],
        }
        for row in rows
    ]


def demand(queryset):
    """What help is being requested?"""
    return {
        "volume": queryset.count(),
        "categoryMix": _counts_by(queryset, "category"),
        "channelMix": _counts_by(queryset, "channel"),
    }


def flow(queryset, *, now=None):
    """Where does work slow down?"""
    now = now or timezone.now()
    unresolved = queryset.exclude(status=TicketStatus.RESOLVED)

    age_rows = (
        unresolved.values("status")
        .annotate(average=Avg(now - F("support_updated_at")))
        .order_by("status")
    )

    # Reopens and hand-offs are only in the audit log — neither leaves a
    # column behind on the ticket. Imported here rather than at module scope
    # to keep this module importable without the audit app loaded.
    from apps.audit.models import AuditLog

    from .lifecycle import AUDIT_ENTITY_TYPE

    # Every matching id comes back into Python and goes out again inside the
    # two counts below, so the SQL text grows with the window rather than
    # staying one statement. Left as it is on purpose, and measured before
    # deciding: 118 ids costs 2ms, 10k costs 98ms, 200k costs 1.4s. The curve
    # is a slope and not a cliff. It was read once as a wall, on the grounds
    # that Postgres accepts at most 65535 bound parameters, but Django's
    # psycopg3 cursor interpolates on the client and sends none, so that limit
    # is not on this path. That holds while server-side binding stays off,
    # which is where settings.py leaves it: turning it on puts the wall back.
    ids = list(queryset.values_list("pk", flat=True))
    audit = AuditLog.objects.filter(entity_type=AUDIT_ENTITY_TYPE, entity_id__in=ids)

    return {
        "unassignedBacklog": unresolved.filter(assignee__isnull=True).count(),
        "ageByStatus": [
            {"status": row["status"], "averageSeconds": _seconds(row["average"])}
            for row in age_rows
        ],
        # Counted per event, not per ticket: a ticket reopened twice counts
        # twice, which is the point of watching this number.
        "reopens": audit.filter(action="reopen").count(),
        # A hand-off is an assign that replaced an existing owner. Picking up
        # an unowned ticket is the other thing that writes this row, and
        # counting it here would make every ticket look like it was passed
        # around once.
        "handOffs": audit.filter(action="assign")
        .exclude(before_state__assignee_id=None)
        .count(),
    }


def service(queryset, *, now=None):
    """How quickly do we respond?"""
    answered = queryset.filter(first_response_at__isnull=False)
    # Counted on the status, which is the column quality() below counts too,
    # so the two "resolved" numbers the dashboard puts on one screen cannot be
    # two different answers to "how many did we resolve". They agree on any
    # data at all, including data no service call can produce, because they
    # ask the same question of the same column.
    #
    # The average underneath still reads resolved_at, which is the column that
    # answers "how long did it take". SQL's AVG skips a row that has no date.
    # So a resolved ticket carrying no resolution date, which is the pair that
    # should never exist, is counted here and left out of the average. It does
    # not pull the two counts apart.
    #
    # This was filtered on resolved_at alone until a seeded demo database put
    # 15 next to 13: two tickets left in progress carrying a resolution date,
    # which the lifecycle cannot do. resolve() writes both columns, and
    # reopen(), set_status() and a reply that moves a ticket to pending all
    # clear resolved_at along with the status. Only a script writing rows
    # straight into the table can separate them.
    resolved = queryset.filter(status=TicketStatus.RESOLVED)
    return {
        "firstResponseSeconds": _seconds(
            answered.aggregate(v=Avg(F("first_response_at") - F("created_at")))["v"]
        ),
        "answeredCount": answered.count(),
        "resolutionSeconds": _seconds(
            resolved.aggregate(v=Avg(F("resolved_at") - F("created_at")))["v"]
        ),
        "resolvedCount": resolved.count(),
        # The same predicate the queue badges tickets with, so the dashboard
        # and the queue can never disagree about what "overdue" means.
        #
        # The definition was widened on 2026-09-04, and it was taken with the
        # client rather than drifted into: asked whether "no first reply within
        # the window" was the right test, they answered "instead of making it
        # just the first response, include follow up responses". So a ticket
        # answered once is no longer safe forever — the clock restarts every
        # time the requester replies and stops every time support does.
        #
        # firstResponseSeconds above is unaffected and still measures the first
        # reply only, which is the question it asks.
        "overdue": queryset.filter(overdue_condition(now)).count(),
    }


def quality(queryset):
    """Did the support help?"""
    total = queryset.count()
    resolved = queryset.filter(status=TicketStatus.RESOLVED).count()

    # People who raised more than one ticket in the window. Counted over
    # requesters rather than tickets: "how many people came back" is the
    # question, and one person with six tickets is one repeat contact.
    repeat = (
        queryset.exclude(created_by__isnull=True)
        .values("created_by_id")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .count()
    )

    return {
        "resolutionRate": round(resolved / total, 4) if total else None,
        "resolvedCount": resolved,
        "totalCount": total,
        "repeatContacts": repeat,
        # Needs the post-resolution survey, which does not exist yet. Reported
        # as an explicit "not collected" rather than as zero: a satisfaction
        # score of 0 is a damning number to invent.
        "satisfaction": None,
        "satisfactionAvailable": False,
    }


def segment(queryset, dimension):
    """One measure broken down, for the dimension the viewer picked."""
    column = SEGMENTS.get(dimension)
    if column is None:
        return None
    return {"dimension": dimension, "buckets": _counts_by(queryset, column)}


def analytics(*, start=None, end=None, dimension=None, now=None):
    now = now or timezone.now()
    queryset = _in_window(live_tickets(), start, end)
    return {
        "window": {
            "from": start.isoformat() if start else None,
            "to": end.isoformat() if end else None,
        },
        "demand": demand(queryset),
        "flow": flow(queryset, now=now),
        "service": service(queryset, now=now),
        "quality": quality(queryset),
        "segment": segment(queryset, dimension) if dimension else None,
        "dimensions": list(SEGMENTS),
    }
