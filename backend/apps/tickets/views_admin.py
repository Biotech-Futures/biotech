"""The support side of the ticket system.

Kept in its own module rather than folded into views.py, which the platform's
single-file convention would suggest. The reason is that these two files are
the two sides of the internal-note rule: one audience must never see them,
the other works in them. Keeping them apart means a reviewer can read either
file and know which audience it serves without checking every queryset.

Everything here is gated on IsSupportScoped — admins included, since every
admin can work the queue. The exception is granting and revoking the support
role itself, which only admins may do.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
import re
from datetime import datetime, time, timedelta, timezone as dt_timezone

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin.permissions import IsAdminScoped
from apps.audit.models import AuditLog
from apps.audit.services import log_audit_event
from apps.common.rbac import user_has_role
from apps.common.role_names import ROLE_STUDENT
from apps.common.storage import serve_managed_file

from .models import (
    SupportScope,
    Ticket,
    TicketAttachment,
    TicketChannel,
    TicketMessage,
    TicketMessageType,
    TicketStatus,
)
from .permissions import IsSupportScoped
from .serializers_admin import (
    BulkAssignSerializer,
    SupportMessageSerializer,
    SupportScopeGrantSerializer,
    TicketPatchSerializer,
)
from .services import analytics as analytics_service
from .services import lifecycle
from .services.paging import (
    after_cursor,
    as_at,
    cursor_for,
    cursor_from,
    snapshot_from,
    stamp,
)
from .services.attachments import stored_attachments, ticket_files
from .services.queue import (
    apply_filters,
    database_id,
    assignee_filter_options,
    known_regions,
    live_tickets,
    overdue_ids,
    summary,
    support_capable_users,
)
from .views import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MessageWriteThrottle,
    _page_params,
)

User = get_user_model()

SUPPORT_PERMISSIONS = [IsAuthenticated, IsSupportScoped]


# "2026-09-02" names a day; "2026-09-02T00:00:00Z" names an instant.
_NAMES_A_WHOLE_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _window_bound(raw, name, *, closes_window=False):
    """A date or datetime from the query string, as an aware UTC instant.

    A bare date is read as UTC midnight, which is the same rule the ticket
    numbering counter uses (DEC-019). Sydney is 10-11 hours ahead, so a
    viewer asking for "1 March" gets a window that opens at 11am their time —
    surprising, but consistent across the product and stable across daylight
    saving, which a local-midnight rule is not.
    """
    if not raw:
        return None

    # Both parsers have the same trap and they trip on different inputs, so
    # both need the guard. Each returns None for a string that does not look
    # like its format, but RAISES ValueError for one that looks right and
    # holds impossible numbers:
    #
    #   "2026-02-30"            parse_datetime -> None      parse_date -> raises
    #   "2026-13-45T00:00:00Z"  parse_datetime -> raises    parse_date -> None
    #
    # Unguarded, either shape is a 500 that any signed-in agent can trigger
    # from the query string. Guarding only one leaves the other class open,
    # which is how the bare-date form survived the first pass.
    try:
        parsed = parse_datetime(raw)
    except ValueError:
        parsed = None
    if parsed is None:
        try:
            day = parse_date(raw)
        except ValueError:
            day = None
        if day is None:
            raise serializers.ValidationError(
                {name: f"{name} must be a date (YYYY-MM-DD) or an ISO 8601 datetime."}
            )
        parsed = datetime.combine(day, time.min)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)

    # A bare date names a whole day, and the window is half-open
    # ([from, to)), so the closing bound has to be the start of the day
    # *after* the one the reader typed. Without this, "to = today" reads as
    # "before today began" and a dashboard covering a month that includes
    # today reports zero for it — a report that confidently states a wrong
    # number, which is worse than one that errors.
    #
    # 🔴 This is the only place that may make this correction. Two others look
    # like they would work and do not: widening analytics.py's `created_at__lt`
    # to `__lte` still excludes the day, because the bound is that day's
    # midnight either way; and correcting it again in the browser would add
    # the day twice. An explicit datetime ("...T00:00:00Z") is left alone —
    # somebody who typed a time meant that instant.
    #
    # Both steps below can leave the range datetime can hold, and both of them
    # raise OverflowError rather than returning something wrong. "9999-12-31"
    # is the last day there is, so the correction above walks off the end of
    # it; and an offset moves the instant too, so "9999-12-31T23:59:59-11:00"
    # and "0001-01-01T00:00:00+14:00" fall off either end once they are read
    # as UTC. Left alone, the second class does not fail here at all. It fails
    # far downstream in the database layer, as a 500 from a value this
    # function already accepted.
    try:
        if closes_window and _NAMES_A_WHOLE_DAY.match(raw.strip()):
            parsed += timedelta(days=1)
        # Normalised here, which is what the docstring above promises and what
        # the window echoed back to the reader has always shown.
        parsed = parsed.astimezone(dt_timezone.utc)
    except OverflowError:
        raise serializers.ValidationError(
            {name: f"{name} is outside the range of dates a report can cover."}
        )
    return parsed


def _person(user):
    if user is None:
        return None
    name = f"{user.first_name} {user.last_name}".strip()
    return {"id": user.pk, "name": name or user.email}


def _requester(ticket):
    user = ticket.created_by
    if user is None:
        return None
    return {
        **_person(user),
        "email": user.email,
        "region": ticket.region,
        "registeredAt": user.date_joined,
    }


def _queue_row(ticket, *, overdue):
    return {
        "id": ticket.pk,
        "ticketNumber": ticket.ticket_number,
        "user": {
            "name": _person(ticket.created_by)["name"] if ticket.created_by else None,
            "region": ticket.region,
            # Derived, not stored. Anonymous submission is not built and is
            # now closed rather than pending: asked on 2026-09-04 whether
            # "people need to be signed in to raise a ticket, but they do not
            # need to be registered in any programme" was right, the client
            # answered "Correct". So this is always false — the only
            # requester-less tickets are the ones screening raises, and the
            # channel check excludes those.
            #
            # Kept rather than deleted. It is a shipped field in a payload the
            # admin app parses strictly, and the comment below is the clearest
            # surviving explanation of what a null created_by means, which the
            # PROTECT change and the user purge both depend on.
            #
            # It reads true for no other case now. It used to: created_by was
            # SET_NULL, and the admin app hard-deletes users, so a portal
            # ticket whose requester had been deleted landed here reading
            # "anonymous" when what had happened was an account being removed.
            # created_by is PROTECT as of 0004 — a person with tickets cannot
            # be deleted without purging them — so null means "there was never
            # a person here", which is the only thing this flag should mean.
            "anonymous": ticket.created_by_id is None and ticket.channel != TicketChannel.AI_SCREENING,
        },
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "assignee": _person(ticket.assignee),
        # The support clock, not the requester's: this column is "when did
        # anything last happen", internal notes included.
        "supportUpdatedAt": ticket.support_updated_at,
        "overdue": overdue,
    }


def _support_message(message):
    return {
        "id": message.pk,
        "messageType": message.message_type,
        "body": message.body,
        "author": _person(message.author),
        "createdAt": message.created_at,
        "attachments": [
            {
                "id": attachment.pk,
                "filename": attachment.original_filename,
                "mimeType": attachment.mime_type,
                "size": attachment.size,
            }
            for attachment in message.attachments.all()
        ],
    }


def _detail(ticket, *, overdue):
    messages = (
        ticket.messages.filter(deleted_at__isnull=True)
        .order_by("created_at")
        .select_related("author")
        .prefetch_related("attachments")
    )
    return {
        "id": ticket.pk,
        "ticketNumber": ticket.ticket_number,
        "subject": ticket.subject,
        "body": ticket.body,
        "category": ticket.category,
        "status": ticket.status,
        "priority": ticket.priority,
        "channel": ticket.channel,
        "region": ticket.region,
        "requester": _requester(ticket),
        "assignee": _person(ticket.assignee),
        "createdAt": ticket.created_at,
        "updatedAt": ticket.updated_at,
        "supportUpdatedAt": ticket.support_updated_at,
        "firstResponseAt": ticket.first_response_at,
        "resolvedAt": ticket.resolved_at,
        "overdue": overdue,
        # Internal notes included: this is the side of the wall that works in
        # them.
        "messages": [_support_message(m) for m in messages],
    }


def _get_ticket_or_none(ticket_id):
    return (
        live_tickets()
        .select_related("created_by", "assignee")
        .filter(pk=ticket_id)
        .first()
    )


def _not_found(what="Ticket"):
    return Response(
        {"msg": f"{what} not found", "data": None},
        status=status.HTTP_404_NOT_FOUND,
    )


class TicketQueueView(APIView):
    permission_classes = SUPPORT_PERMISSIONS

    def get(self, request):
        page, limit = _page_params(request)
        try:
            cursor = cursor_from(request)
        except ValueError:
            return Response(
                {"msg": "Malformed paging cursor", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if cursor is not None and not (request.query_params.get("asOf") or "").strip():
            # A cursor names a place inside one snapshot, so it means nothing
            # without the snapshot it came from. Answering anyway would page
            # through a set assembled a moment later — the two-requests-one-walk
            # mistake this module was rewritten to end, arriving by a new door.
            return Response(
                {"msg": "A paging cursor must be sent with the snapshot it came from",
                 "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # The snapshot and the cursor are one thing: a walk. A snapshot on its
        # own would freeze the set for an offset, and an offset over a set that
        # can shrink is the defect itself — a worked ticket leaves, every row
        # behind it moves up, and the row that was first on the next page slides
        # onto the page just read. So a request without a cursor is a fresh look
        # whatever else it carries.
        as_of = snapshot_from(request) if cursor is not None else timezone.now()
        # Ticket.objects, not live_tickets(): as_at() decides membership at
        # the snapshot instant, and a ticket deleted mid-walk has to stay in
        # the set until somebody opens it.
        # See services/paging.py for the measurement that established this.
        queryset = as_at(
            apply_filters(
                Ticket.objects.select_related("created_by", "assignee"),
                region=request.query_params.get("region"),
                status=request.query_params.get("status"),
                category=request.query_params.get("category"),
                assignee=request.query_params.get("assignee"),
                priority=request.query_params.get("priority"),
                search=request.query_params.get("search"),
            ),
            as_of,
            activity_field="support_updated_at",
        )

        total = queryset.count()
        # A cursor continues a walk; its absence starts one. Choosing a page
        # number out of the footer is the reader skipping ahead on purpose, and
        # arrives here as a fresh snapshot with an offset — self-consistent,
        # because one query at one instant cannot disagree with itself.
        offset = 0 if cursor is not None else (page - 1) * limit
        window = after_cursor(queryset, cursor, activity_field="support_updated_at")
        # One row past the page: hasMore has to describe what is left in front
        # of the cursor, and a count of the whole set cannot say that.
        found = list(window[offset:offset + limit + 1])
        has_more = len(found) > limit
        tickets = found[:limit]
        flagged = overdue_ids(tickets)
        rows = [_queue_row(t, overdue=t.pk in flagged) for t in tickets]
        return Response({
            "msg": "Ticket queue retrieved successfully",
            "data": {
                "items": rows,
                "total": total,
                "page": page,
                "limit": limit,
                "hasMore": has_more,
                # Echoed so the client can send them back on the next page.
                # Always in the "Z" form: "+00:00" is what gets mangled in a
                # query string, so the values we hand out cannot carry it.
                "asOf": stamp(as_of),
                "after": (
                    cursor_for(tickets[-1], activity_field="support_updated_at")
                    if tickets else None
                ),
            },
        })


class TicketSummaryView(APIView):
    permission_classes = SUPPORT_PERMISSIONS

    def get(self, request):
        return Response({
            "msg": "Ticket summary retrieved successfully",
            "data": summary(),
        })


class TicketAssigneesView(APIView):
    permission_classes = SUPPORT_PERMISSIONS

    def get(self, request):
        assignable_ids = set(support_capable_users().values_list("pk", flat=True))
        return Response({
            "msg": "Assignees retrieved successfully",
            # One list, two questions. The filter dropdown needs everybody who
            # could own a ticket, including deactivated agents — their tickets
            # do not move when the account is switched off, and filtering is
            # the only way to find that work in bulk. The assign dropdown must
            # offer only people who can actually pick it up. So each row says
            # which it is and the two consumers decide for themselves.
            #
            # "assignable" has to mean what the write path accepts, which is
            # membership of support_capable_users(). It used to read is_active,
            # and those are not the same set: revoking somebody's support row
            # leaves the account active, so they stayed in the assign dropdown
            # while TicketPatchSerializer — which validates against
            # support_capable_users() — refused them with a 400. The agent got
            # an offered name and an unexplained failure.
            "data": [
                {**_person(user), "assignable": user.pk in assignable_ids}
                for user in assignee_filter_options()
            ],
        })


class TicketRegionsView(APIView):
    permission_classes = SUPPORT_PERMISSIONS

    def get(self, request):
        return Response({
            "msg": "Regions retrieved successfully",
            "data": known_regions(),
        })


class TicketAdminDetailView(APIView):
    permission_classes = SUPPORT_PERMISSIONS

    def get(self, request, ticket_id):
        ticket = _get_ticket_or_none(ticket_id)
        if ticket is None:
            return _not_found()
        return Response({
            "msg": "Ticket retrieved successfully",
            "data": _detail(ticket, overdue=ticket.pk in overdue_ids([ticket])),
        })

    def patch(self, request, ticket_id):
        ticket = _get_ticket_or_none(ticket_id)
        if ticket is None:
            return _not_found()

        serializer = TicketPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        changes = serializer.validated_data

        # One transaction around the whole request, not one per field.
        #
        # priority and status may arrive together, and they used to commit
        # separately: the priority write landed, then the status write found
        # the ticket deleted and the view answered 404 "Ticket not found".
        # The caller reads that as "nothing happened" and the priority change
        # is already in the database, with an audit row for it. Either the
        # request happened or it did not.
        #
        # The lifecycle functions open their own atomic blocks; nesting turns
        # those into savepoints, which is what makes rolling the whole thing
        # back possible.
        try:
            with transaction.atomic():
                self._apply(request, ticket, changes)
        except lifecycle.TicketGone:
            return _not_found()

        ticket.refresh_from_db()
        return Response({
            "msg": "Ticket updated successfully",
            "data": _detail(ticket, overdue=ticket.pk in overdue_ids([ticket])),
        })

    def _quiet_field(self, request, ticket, changes, field, action):
        """Change one field that carries no timeline entry and sends no email.

        priority and category are both like this, and for the same reason. The
        requester can see the value — they chose the category themselves, and
        since 2026-09-04 they choose the priority too — but the *change* is a
        triage decision, not a message. So it moves the support queue's clock
        and never the requester's: their list does not reorder, nothing lands
        in their inbox, and the timeline stays a record of what was said
        rather than of how the ticket was filed. The audit log is where the
        change is recorded, and it is complete there.
        """
        if field not in changes:
            return
        after = changes[field]
        if getattr(ticket, field) == after:
            return
        # Two writes, so one transaction: every other state change on this
        # ticket gets its audit row and its update together, and a crash
        # between them here would leave a history entry for a change the
        # queue never made.
        with transaction.atomic():
            lifecycle._lock(ticket)
            # Read after the lock, not before: _lock refreshes in place, so a
            # value captured earlier is the one another request may already
            # have replaced. Same shape as _assign_one.
            before = getattr(ticket, field)
            # Re-checked against the committed value: another request may have
            # set the same value while this one waited for the lock, and an
            # audit row saying "high -> high" is noise in the one place that
            # has to stay readable.
            if before == after:
                return
            log_audit_event(
                actor=request.user,
                entity_type=lifecycle.AUDIT_ENTITY_TYPE,
                entity_id=ticket.pk,
                action=action,
                before_state={field: before},
                after_state={field: after},
            )
            lifecycle._touch(ticket, user_visible=False, **{field: after})

    def _apply(self, request, ticket, changes):
        # Priority and category first, on their own terms. Both are triage
        # fields: see _quiet_field for why neither writes a timeline message.
        self._quiet_field(request, ticket, changes, "priority", "priority")
        # Re-filing. With three categories a wrong one was tolerable; with the
        # client's eight, two of which ("General Question" and "Other") are
        # near-synonyms, an agent will routinely know a ticket is filed wrong.
        # Without this the p52 category breakdown slowly fills with noise
        # nobody is able to correct.
        self._quiet_field(request, ticket, changes, "category", "category")

        if "status" in changes:
            lifecycle.set_status(
                ticket=ticket, new_status=changes["status"], actor=request.user
            )
        elif "assignee" in changes:
            lifecycle.assign(
                ticket=ticket, actor=request.user, assignee=changes["assignee"]
            )


class TicketDeleteView(APIView):
    """Remove a duplicate, a test submission or spam from the queue.

    Admins only, not every agent (DEC-024). Deleting is the one action here
    that no other action undoes: there is no restore path in the product, and
    the ticket leaves the requester's own list as well as the queue.
    """

    permission_classes = [IsAuthenticated, IsAdminScoped]

    def delete(self, request, ticket_id):
        ticket = _get_ticket_or_none(ticket_id)
        if ticket is None:
            # Already deleted tickets are not in live_tickets(), so deleting
            # one twice is a 404 rather than a second audit row.
            return _not_found()
        if not lifecycle.soft_delete(ticket=ticket, actor=request.user):
            # Lost the race with another admin's delete. Same answer as
            # arriving a moment later, and no second audit row.
            return _not_found()
        return Response({"msg": "Ticket deleted", "data": None})


class TicketHistoryView(APIView):
    """Who moved this ticket, and from what to what.

    Reads AuditLog directly rather than reusing the platform's audit endpoint,
    which is gated on is_staff and would shut out an agent who is not also an
    admin. Ordered explicitly: the model's own default is newest-first, which
    is the opposite of a history.
    """

    permission_classes = SUPPORT_PERMISSIONS

    def get(self, request, ticket_id):
        ticket = _get_ticket_or_none(ticket_id)
        if ticket is None:
            return _not_found()
        rows = (
            AuditLog.objects.filter(
                entity_type=lifecycle.AUDIT_ENTITY_TYPE, entity_id=ticket.pk
            )
            .select_related("actor_user")
            .order_by("created_at")
        )
        return Response({
            "msg": "Ticket history retrieved successfully",
            "data": [
                {
                    "id": row.pk,
                    "action": row.action,
                    "actor": _person(row.actor_user),
                    "beforeState": row.before_state,
                    "afterState": row.after_state,
                    "createdAt": row.created_at,
                }
                for row in rows
            ],
        })


class TicketAnalyticsView(APIView):
    """The dashboard behind the client's p52 (four measure groups, six
    segments).

    One endpoint for the whole page rather than one per chart: every measure
    reads the same filtered set, and splitting them would let two tiles on one
    screen disagree because they were fetched a second apart.

    Support-visible, not admin-only. They are the people the numbers are
    about, and "how long are we taking to answer" is not management-only
    information on a team this size.
    """

    permission_classes = SUPPORT_PERMISSIONS

    def get(self, request):
        start = _window_bound(request.query_params.get("from"), "from")
        end = _window_bound(request.query_params.get("to"), "to", closes_window=True)
        if start and end and start > end:
            raise serializers.ValidationError(
                {"from": "from must be earlier than to."}
            )

        dimension = request.query_params.get("dimension") or None
        if dimension and dimension not in analytics_service.SEGMENTS:
            # Named explicitly rather than ignored: a typo that silently
            # returns the whole set looks like a segment with one bucket.
            raise serializers.ValidationError({
                "dimension": f"Unknown dimension. Choose one of: "
                             f"{', '.join(analytics_service.SEGMENTS)}."
            })

        return Response({
            "msg": "Ticket analytics retrieved successfully",
            "data": analytics_service.analytics(
                start=start, end=end, dimension=dimension
            ),
        })


class TicketAuditView(APIView):
    """Every recorded ticket action, including the ones on deleted tickets.

    The per-ticket history endpoint above cannot show a deletion: it looks the
    ticket up through live_tickets() first, so the moment a ticket is deleted
    its own history 404s. The delete dialog tells an admin the record is kept,
    and until this existed there was nowhere that record could be read.

    Support-visible, matching the per-ticket history rather than the
    admin-only delete action. An agent who watched a ticket vanish from the
    queue can see that it was deleted and by whom, instead of wondering
    whether they imagined it.

    Deleted rows carry the ticket number and subject in before_state, which is
    why this can identify them without joining back to a row no queryset
    returns.
    """

    permission_classes = SUPPORT_PERMISSIONS

    def get(self, request):
        page, limit = _page_params(request)
        offset = (page - 1) * limit

        rows = AuditLog.objects.filter(
            entity_type=lifecycle.AUDIT_ENTITY_TYPE
        ).select_related("actor_user")

        action = request.query_params.get("action")
        if action:
            # Free text on this model — log_audit_event does not validate
            # against ActionChoices, and the ticket module writes seven values
            # of which only three are in that enum. An unknown value filters
            # to nothing rather than erroring, matching the string columns on
            # the queue endpoint.
            rows = rows.filter(action=action)

        actor = request.query_params.get("actor")
        if actor:
            # The same reader the queue's ?assignee= uses. This had its own
            # copy that stopped at int(), so a huge number here answered 200
            # on PostgreSQL and 500 on SQLite while the neighbouring endpoint
            # answered 400 on both.
            rows = rows.filter(actor_user_id=database_id(actor, "actor"))

        # Newest first: this is a log to scan, not a story to read, which is
        # the opposite of the per-ticket history right above.
        rows = rows.order_by("-created_at", "-id")

        total = rows.count()
        page_rows = list(rows[offset:offset + limit])
        return Response({
            "msg": "Ticket audit retrieved successfully",
            "data": {
                "items": [
                    {
                        "id": row.pk,
                        "ticketId": row.entity_id,
                        "action": row.action,
                        "actor": _person(row.actor_user),
                        "beforeState": row.before_state,
                        "afterState": row.after_state,
                        "createdAt": row.created_at,
                    }
                    for row in page_rows
                ],
                "total": total,
                "page": page,
                "limit": limit,
                # hasMore, not has_more: the other ticket endpoints use this
                # spelling and the platform is split between the two.
                "hasMore": offset + len(page_rows) < total,
            },
        })


class TicketSupportMessageView(APIView):
    permission_classes = SUPPORT_PERMISSIONS
    # The requester's reply endpoint carries the same cap. This one writes the
    # same blobs through the same stored_attachments, so leaving it off here
    # would have been a cap on one door of a room with two.
    throttle_classes = [MessageWriteThrottle]

    def post(self, request, ticket_id):
        ticket = _get_ticket_or_none(ticket_id)
        if ticket is None:
            return _not_found()

        serializer = SupportMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message_type = serializer.validated_data["messageType"]
        body = serializer.validated_data["body"]
        move_to_pending = serializer.validated_data["moveToPending"]
        files = request.FILES.getlist("files")

        try:
            with stored_attachments(files) as attachments:
                if message_type == TicketMessageType.INTERNAL_NOTE:
                    lifecycle.add_internal_note(
                        ticket=ticket, actor=request.user, body=body,
                        attachments=attachments,
                    )
                else:
                    lifecycle.add_support_reply(
                        ticket=ticket, actor=request.user, body=body,
                        attachments=attachments, move_to_pending=move_to_pending,
                    )
        except lifecycle.TicketGone:
            return _not_found()

        ticket.refresh_from_db()
        return Response(
            {
                "msg": "Message added successfully",
                "data": _detail(ticket, overdue=ticket.pk in overdue_ids([ticket])),
            },
            status=status.HTTP_201_CREATED,
        )


class TicketBulkAssignView(APIView):
    permission_classes = SUPPORT_PERMISSIONS

    def post(self, request):
        serializer = BulkAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = lifecycle.bulk_assign(
            ticket_ids=serializer.validated_data["ticketIds"],
            assignee=serializer.validated_data["assigneeId"],
            actor=request.user,
        )
        return Response({
            "msg": "Bulk assignment completed",
            "data": {"results": results},
        })


class TicketAdminAttachmentDownloadView(APIView):
    """Same download, without the requester-side conditions.

    Deliberately not sharing an implementation with the requester's download
    view: that view's queryset is its access control, and a shared helper with
    a flag is one wrong default away from serving internal notes to students.
    """

    permission_classes = SUPPORT_PERMISSIONS

    def get(self, request, ticket_id, attachment_id):
        attachment = TicketAttachment.objects.filter(
            pk=attachment_id,
            message__ticket_id=ticket_id,
            message__ticket__deleted_at__isnull=True,
            message__deleted_at__isnull=True,
        ).first()
        if attachment is None:
            return _not_found("Attachment")
        return serve_managed_file(
            resolve_url=ticket_files.resolve_url,
            open_file=ticket_files.open,
            storage_key=attachment.storage_key,
            filename=attachment.original_filename,
            mime_type=attachment.mime_type,
            size=attachment.size,
            as_attachment=True,
        )


def _grant_refusal(user):
    """Why this account must not go on the support roster, or None.

    The endpoint is admin-only and the grant is a deliberate click, so this is
    not a permission hole — it is the missing guard rail beside one. The
    candidate list shows a name and an email and no role, and the Grant button
    has no confirmation, while Revoke beside it does. A mis-click on the wrong
    row put a student account on the roster, and a student on the roster reads
    every ticket on the platform: other students' names, email addresses and
    whatever they wrote about their problem.

    user_has_role rather than comparing a role string: role_name is free text
    with a case-sensitive unique index, so "Student" and "student" are two rows
    and both exist in real data on this platform. A bare == lets the capitalised
    one straight through.
    """
    if user_has_role(user, ROLE_STUDENT):
        return ("Students cannot be given support queue access. Change their "
                "role first if this is not a student account.")
    if user.account_status in User.INACTIVE_LOGIN_STATUSES:
        # A switched-off account cannot sign in, so the grant does nothing
        # today. It is not harmless, though: the row it writes is a standing
        # decision, and reactivating the account turns it into real access to
        # every ticket on the platform without anybody deciding that a second
        # time.
        #
        # INACTIVE_LOGIN_STATUSES rather than is_active, which is a wider set.
        # "Invited" and "pending" are is_active=False as well, and granting to
        # somebody who has been invited but has not finished onboarding is a
        # thing an admin may legitimately want to do first. The roster ordering
        # below already expects those rows.
        return ("This account is switched off, so it cannot work the queue. "
                "Reactivate it first, then grant support access.")
    return None


class SupportScopeView(APIView):
    """Who is on the support roster.

    Admins only. Every admin can already work the queue, so this is about
    granting the role to someone who is not an admin — the client will ask
    "how do I add a support person?" at handover, and "insert a row with the
    Django shell" is not an answer.
    """

    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        rows = (
            SupportScope.objects.select_related("user")
            .annotate(
                # What revoking would strand. Counted here rather than by the
                # screen asking per row, and resolved tickets are excluded
                # because nobody has to pick those up again.
                open_tickets=Count(
                    "user__tickets_assigned",
                    filter=Q(user__tickets_assigned__deleted_at__isnull=True)
                    & ~Q(user__tickets_assigned__status=TicketStatus.RESOLVED),
                )
            )
            # first_name alone is not a total order, and it is blank for anyone
            # invited but never onboarded — those rows would shuffle between
            # requests, which reads as the table losing people.
            .order_by("user__first_name", "user__last_name", "user__email")
        )
        return Response({
            "msg": "Support roster retrieved successfully",
            "data": [
                {
                    **_person(row.user),
                    "email": row.user.email,
                    "openTickets": row.open_tickets,
                    # Switching an agent off does not delete their row here,
                    # and that is deliberate: the two are independent on this
                    # platform (see queue.support_capable_users). The cost is
                    # that a name on this list may be an account nobody can
                    # sign into, and until this field existed the screen had
                    # no way to tell the reader which.
                    "accountStatus": row.user.account_status,
                }
                for row in rows
            ],
        })

    def post(self, request):
        serializer = SupportScopeGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(pk=serializer.validated_data["userId"]).first()
        if user is None:
            return _not_found("User")

        refusal = _grant_refusal(user)
        if refusal is not None:
            return Response({"msg": refusal, "data": None},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            _, created = SupportScope.objects.get_or_create(user=user)
            if created:
                log_audit_event(
                    actor=request.user,
                    entity_type="support_scope",
                    entity_id=user.pk,
                    action="create",
                    before_state=None,
                    after_state={"user_id": user.pk},
                )
        return Response(
            {"msg": "Support access granted", "data": {**_person(user), "email": user.email}},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SupportScopeRevokeView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def delete(self, request, user_id):
        scope = SupportScope.objects.filter(user_id=user_id).first()
        if scope is None:
            return _not_found("Support access")
        with transaction.atomic():
            log_audit_event(
                actor=request.user,
                entity_type="support_scope",
                entity_id=user_id,
                action="delete",
                before_state={"user_id": user_id},
                after_state=None,
            )
            scope.delete()
        return Response({"msg": "Support access revoked", "data": None})
