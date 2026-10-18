"""Snapshot paging for the two ticket lists.

Both lists are ordered by a column that moves while people read them: the
support queue by last support activity, the requester's own list by last
update. That is what the reader wants to see — the ticket somebody just
replied to belongs at the top — and it is also what makes paging them hard.

**Two earlier attempts got this wrong, and both mistakes are worth keeping.**

The first filtered the set to ``activity <= asOf``. Each page's *contents*
hold still, but a row that gains activity mid-walk leaves the set entirely.
The set shrinks by one, every row behind the departed one moves up a
position, and the row that had been first on the next page slides onto the
page just read. Measured: paging a 30-row queue five at a time while one
already-read ticket got an internal note returned 29 distinct rows, and the
missing one had not been touched at all.

The second — the one this module shipped with — kept every row in the set and
capped the sort key instead: ``LEAST(activity, asOf)``. The reasoning written
here was that a row whose sort value rises moves *towards the front*, pushing
the rows between it and its old position backwards, into territory the reader
has not covered yet; worst case, seeing a row twice. That paragraph ended
"No row can move forwards past the reader", and it contradicted its own
previous sentence. The row that moves *is* the row that passes the reader.
``asOf`` is the upper bound of that column, so a capped row does not move
towards the front, it moves to position 0 — behind any reader who is past
page one, on every page, for the rest of the walk. Measured on Postgres:
200 tickets, ten to a page, an internal note added to three of them while the
reader was on page two; those exact three were served on no page, and the
last page still reported "20 of 20".

There is no ordering that makes OFFSET safe here. Any row that changes
position while a walk is in progress either crosses the reader itself or
shifts the rows behind it across the reader; a set that can shrink does the
same thing one row at a time. Holding the *contents* still is not enough —
what has to hold still is the reader's place in them.

So the walk is anchored to the last row it served, not to a count of rows it
has passed:

* **Membership is decided at the snapshot instant.** ``created_at <= asOf``
  keeps tickets raised mid-walk out, ``activity <= asOf`` drops a row the
  moment somebody works it, and ``deleted_at`` null or later than the
  snapshot keeps a ticket deleted mid-walk in. Which of those last two claims
  a deletion depends on the column the caller walks. ``soft_delete`` writes
  ``deleted_at`` and ``support_updated_at`` in one statement, so on the
  support queue the row leaves through the activity filter and never reaches
  the ``deleted_at`` clause. The requester's own list walks ``updated_at``,
  which a deletion does not touch, and there the ``deleted_at`` clause is the
  only thing holding the row in. Both answers are decided here rather than by
  the caller, which is why the queryset handed in must not have excluded
  soft-deleted rows already.
* **The order among the survivors cannot change.** Every row still in the set
  has the activity it had at the snapshot, because a row whose activity moved
  is no longer in the set. ``-pk`` breaks ties: rows sharing a timestamp are
  not a total order on their own, and Postgres may return them in a different
  sequence per query, which loses rows by a second, independent route.
* **The cursor is that order's own key**, ``(activity, pk)``. Asking for
  everything strictly after it cannot skip a row, whatever enters or leaves
  the set in front of or behind the reader.

What the reader sees when a ticket is worked mid-walk: that one ticket
disappears from the rest of this walk, and comes back on the next refresh.
It is the row somebody just touched, so its absence is the one absence a
support agent can account for — unlike the old behaviour, which hid a row
nobody had touched. A ticket deleted mid-walk stays in the requester's walk
until they open it, and the detail view already answers "That ticket could
not be opened. It may have been deleted." On the support queue it goes at
once, for the reason in the first bullet above: deleting a ticket moves the
column that queue is ordered by. Measured on Postgres: 60 tickets, ten to a
page, three deleted while the reader was on page one; the other 57 were
served in order, none twice and none missed.

**Jumping to a page number is a different thing and is served differently.**
The guarantee above is about a walk: a request that carries a cursor is
continuing one, and within one walk nothing is skipped. Choosing page 7 out
of the footer is the reader deciding to skip pages 2 to 6, so it starts a
fresh snapshot and takes an offset into it. A single query at a single
instant is self-consistent; the defect above only ever lived in the gap
between two requests that thought they were the same walk. That is what lets
this list keep numbered paging.

Only Next carries a cursor today. The support queue counts anything other
than one step forward as a jump, Previous included, so stepping back opens a
fresh snapshot and takes an offset into it. Nothing is skipped by that: rows
that moved while the reader was ahead of them can be served a second time on
the way back, over ground the reader has already covered. Closing it would
need no reverse cursor. Page N-1 is reached with the forward cursor that
page N-2 handed out, and the client already holds it.
"""

from datetime import timezone as dt_timezone

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def snapshot_from(request):
    """The moment this paging walk is reading.

    An absent, unreadable or impossible stamp starts a fresh walk rather than
    raising. The failure being guarded against is a stamp arriving mangled
    mid-walk, and a current snapshot is a better answer to that than a 400.
    """
    raw = (request.query_params.get("asOf") or "").strip()
    if not raw:
        return timezone.now()

    parsed = _parse_stamp(raw)
    return timezone.now() if parsed is None else parsed


def _parse_stamp(raw):
    """A timestamp off the wire, or None if it is not one.

    "+00:00" in a query string decodes to a space unless it was encoded. A
    stamp mangled that way parses as nothing, the snapshot silently stops
    applying, and tests that only check "no row was lost" stay green, because
    not filtering loses no rows either. Repaired here as the second of two
    defences; the first is that the clients encode it and that this module
    hands out the "Z" form, which has no "+" to lose.

    parse_datetime returns None for a string that does not look like a
    timestamp but RAISES for one that looks like a timestamp and holds
    impossible numbers, so an unhandled "2026-13-45T99:99:99Z" is a 500
    anybody can trigger from the query string.
    """
    try:
        parsed = parse_datetime(raw.replace(" ", "+"))
        if parsed is None:
            return None
        if timezone.is_naive(parsed):
            # django.utils.timezone.utc was removed in Django 5.
            return timezone.make_aware(parsed, dt_timezone.utc)
        # Normalise here rather than leave the offset on. A stamp at either end
        # of the calendar with an offset that pushes it past the end is a legal
        # datetime until something shifts it to UTC, and the thing that shifts
        # it is the database layer, far from any handler that could answer 400.
        # Doing it here means the OverflowError lands next to the other ways a
        # stamp can be unreadable, and gets the same answer.
        return parsed.astimezone(dt_timezone.utc)
    except (ValueError, OverflowError):
        return None


def as_at(queryset, as_of, *, activity_field):
    """The list as it stood at ``as_of``, in an order that cannot change.

    ``queryset`` must NOT already exclude soft-deleted rows: this decides
    membership itself, and a ticket deleted after the snapshot has to stay in
    on any column a deletion does not move. The requester's list walks
    ``updated_at`` and is the caller that rests on it. The support queue walks
    ``support_updated_at``, which ``soft_delete`` writes in the same statement
    as ``deleted_at``, so there the row leaves through the activity filter one
    line above and the ``deleted_at`` clause never sees it. See the module
    docstring for why.
    """
    return (
        queryset
        .filter(created_at__lte=as_of)
        .filter(**{f"{activity_field}__lte": as_of})
        .filter(Q(deleted_at__isnull=True) | Q(deleted_at__gt=as_of))
        .order_by(f"-{activity_field}", "-pk")
    )


def cursor_for(row, *, activity_field):
    """The wire form of one row's place in the order above.

    Both halves of the sort key, in the order they sort, joined by a character
    that appears in neither: a timestamp in the "Z" form has no underscore and
    a primary key has no characters at all beyond digits.
    """
    return f"{stamp(getattr(row, activity_field))}_{row.pk}"


def cursor_from(request):
    """The cursor this request is continuing from, or None.

    Raises ValueError for a cursor that arrived but could not be read. That is
    deliberately not the same as no cursor at all: silently starting over
    would serve page one under a later page's number and lose every row the
    reader had not reached, which is the defect this module exists to close.
    A stamp that cannot be read is a bug in the client or a tampered URL, and
    both are better answered out loud.
    """
    raw = (request.query_params.get("after") or "").strip()
    if not raw:
        return None

    key, _, raw_pk = raw.rpartition("_")
    if not key or not raw_pk.isdigit():
        raise ValueError("Malformed paging cursor")

    moment = _parse_stamp(key)
    if moment is None:
        raise ValueError("Malformed paging cursor")
    return moment, int(raw_pk)


def after_cursor(queryset, cursor, *, activity_field):
    """Everything strictly after ``cursor`` in the order ``as_at`` produced.

    Descending on both halves, so "after" is "less than": an earlier activity,
    or the same activity and a lower primary key. Skipping the second half
    would drop every row sharing a timestamp with the last one served.
    """
    if cursor is None:
        return queryset
    moment, pk = cursor
    return queryset.filter(
        Q(**{f"{activity_field}__lt": moment})
        | Q(**{activity_field: moment, "pk__lt": pk})
    )


def stamp(moment) -> str:
    """The wire form: always "Z", never "+00:00".

    The value handed out cannot carry the character that gets eaten by an
    un-encoded query string, so a client that forgets to encode still sends
    back something readable.
    """
    return moment.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")
