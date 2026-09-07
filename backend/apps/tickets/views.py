"""The five endpoints a requester can reach.

Everything here answers 404 rather than 403 when someone asks about a ticket
that is not theirs. A 403 confirms the ticket exists, which is enough to walk
the id space and learn how many enquiries the platform has.
"""

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from apps.common.storage import serve_managed_file

from .models import Ticket, TicketAttachment, TicketMessage, TicketMessageType
from .serializers import TicketCreateSerializer, TicketReplySerializer
from .services import lifecycle
from .services.attachments import stored_attachments, ticket_files
from .services.paging import (
    after_cursor,
    as_at,
    cursor_for,
    cursor_from,
    snapshot_from,
    stamp,
)

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
# Only meaningful together with MAX_PAGE_SIZE: the two multiply into the
# largest OFFSET this module can produce, and that product has to stay inside
# a Postgres bigint.
MAX_PAGE = 10_000

# What the requester is told a support reply came from. A role, not a person:
# the platform's users are minors, and nothing in the design asks for staff to
# be named to them.
SUPPORT_AUTHOR_LABEL = "Support"


class WriteOnlyScopedThrottle(ScopedRateThrottle):
    """Rate-limit the writes on a view without touching its reads.

    Submitting a ticket is cheap for the requester and expensive for us: it
    writes blobs to Azure and puts an email on the four-worker pool that also
    carries login codes and password resets. Reading your own list of
    enquiries costs none of that, and throttling it would punish the ordinary
    behaviour of refreshing a page while you wait for an answer.
    """

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().allow_request(request, view)


class MessageWriteThrottle(UserRateThrottle):
    """The cap on adding a message, which submitting a ticket already had.

    Posting a message runs the same stored_attachments as submitting one and
    writes the same blobs to the same place, and this half of the pair had
    nothing on it at all: forty-five replies in a row, all 201.

    Sixty an hour is a message a minute sustained for an hour. Somebody
    writing to a person does not reach it. A loop reaches it in seconds.

    Both message endpoints share this scope, so it is one budget per person
    rather than one per door. The support side is included because it writes
    through the same helper. See views_admin.TicketSupportMessageView.

    The rate sits on the class rather than in DEFAULT_THROTTLE_RATES, which is
    where ticket_create's lives. Deliberate: under that arrangement the scope
    name is spelled in two files, and spelling it differently in one of them
    is an ImproperlyConfigured raised at request time instead of at startup.
    """

    scope = "ticket_message"
    rate = "60/hour"


def _positive_int(raw, default):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _page_params(request):
    page = _positive_int(request.query_params.get("page"), 1)
    limit = _positive_int(request.query_params.get("limit"), DEFAULT_PAGE_SIZE)
    # Over the cap is clamped rather than rejected: a client asking for too
    # much gets less, not an error (04-api-contract §3, DEC-016⑩). Page is
    # capped the same way for a harder reason: past the cap, (page-1)*limit
    # overflows the bigint OFFSET and Postgres raises instead of returning the
    # empty page the client should get.
    return min(page, MAX_PAGE), min(limit, MAX_PAGE_SIZE)


def _my_tickets(user):
    return Ticket.objects.filter(created_by=user, deleted_at__isnull=True)


def _visible_messages(ticket):
    """The timeline as the requester is allowed to see it.

    Internal notes are removed here, at the queryset, and not by the frontend
    choosing what to render. Anything that reaches the serializer has already
    left the building.
    """
    return (
        ticket.messages.filter(deleted_at__isnull=True)
        .exclude(message_type=TicketMessageType.INTERNAL_NOTE)
        .order_by("created_at")
        .prefetch_related("attachments")
    )


def _list_row(ticket):
    return {
        "id": ticket.pk,
        "ticketNumber": ticket.ticket_number,
        "subject": ticket.subject,
        "category": ticket.category,
        "status": ticket.status,
        # Theirs to set and theirs to see (client, 2026-09-04). An agent may
        # change it afterwards and the new value shows here, but that change
        # moves no clock and writes no timeline entry, so this row does not
        # reorder because of it — see lifecycle._touch.
        "priority": ticket.priority,
        # The requester's clock, never support_updated_at.
        "lastUpdated": ticket.updated_at,
    }


def _author_label(message):
    if message.message_type == TicketMessageType.SUPPORT_REPLY:
        return SUPPORT_AUTHOR_LABEL
    if message.message_type == TicketMessageType.USER_MESSAGE and message.author:
        return f"{message.author.first_name} {message.author.last_name}".strip() or None
    return None


def _message_payload(message):
    return {
        "id": message.pk,
        "messageType": message.message_type,
        "body": message.body,
        "author": _author_label(message),
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


def _detail_payload(ticket):
    # Priority is here because the requester chose it. Assignee is still not:
    # naming the agent working a minor's ticket is what DEC-017 rules out, and
    # nothing on this side of the wall needs it.
    return {
        "id": ticket.pk,
        "ticketNumber": ticket.ticket_number,
        "subject": ticket.subject,
        "body": ticket.body,
        "category": ticket.category,
        "status": ticket.status,
        "priority": ticket.priority,
        "createdAt": ticket.created_at,
        "lastUpdated": ticket.updated_at,
        "messages": [_message_payload(m) for m in _visible_messages(ticket)],
    }


class TicketListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    # Generous on purpose: a real person with a real problem raises one or two
    # enquiries. The cap exists to stop a loop, not to ration help.
    throttle_classes = [WriteOnlyScopedThrottle]
    throttle_scope = "ticket_create"

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
            return Response(
                {"msg": "A paging cursor must be sent with the snapshot it came from",
                 "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Tiebroken for the same reason as the support queue: without a second
        # key this is not a total order, and paging over it can skip rows
        # entirely on Postgres. A requester with several enquiries submitted in
        # one sitting is exactly the case that ties.
        # And snapshotted for the other half of the same problem: the sort key
        # is live, so an enquiry that gets a reply while the reader is part
        # way down "Show more" moves under them. Same mechanism as the support
        # queue, one list further from anybody who would notice.
        # Snapshot and cursor travel together — see the support queue and
        # services/paging.py. Without a cursor this is a fresh look.
        as_of = snapshot_from(request) if cursor is not None else timezone.now()
        # Ticket.objects filtered by owner only: as_at() decides membership at
        # the snapshot instant, including whether a ticket deleted mid-walk
        # stays in.
        queryset = as_at(
            Ticket.objects.filter(created_by=request.user),
            as_of,
            activity_field="updated_at",
        )
        total = queryset.count()
        # "Show more" always carries the cursor, so this list is walked and
        # never jumped. The offset branch is here so that page is not a lie if
        # a caller sends one. See services/paging.py.
        offset = 0 if cursor is not None else (page - 1) * limit
        window = after_cursor(queryset, cursor, activity_field="updated_at")
        found = list(window[offset:offset + limit + 1])
        has_more = len(found) > limit
        tickets = found[:limit]
        rows = [_list_row(t) for t in tickets]
        return Response({
            "msg": "Tickets retrieved successfully",
            "data": {
                "items": rows,
                "total": total,
                "page": page,
                "limit": limit,
                "hasMore": has_more,
                "asOf": stamp(as_of),
                "after": (
                    cursor_for(tickets[-1], activity_field="updated_at")
                    if tickets else None
                ),
            },
        })

    def post(self, request):
        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = request.FILES.getlist("files")

        # Uploads first, outside the transaction; the context manager cleans
        # the blobs up if the insert below fails.
        with stored_attachments(files) as attachments:
            ticket = lifecycle.create_ticket(
                user=request.user,
                attachments=attachments,
                **serializer.validated_data,
            )
        return Response(
            {"msg": "Ticket created successfully", "data": _detail_payload(ticket)},
            status=status.HTTP_201_CREATED,
        )


class TicketDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id):
        ticket = _my_tickets(request.user).filter(pk=ticket_id).first()
        if ticket is None:
            return Response(
                {"msg": "Ticket not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({
            "msg": "Ticket retrieved successfully",
            "data": _detail_payload(ticket),
        })


class TicketMessageCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MessageWriteThrottle]

    def post(self, request, ticket_id):
        ticket = _my_tickets(request.user).filter(pk=ticket_id).first()
        if ticket is None:
            # Same answer as the read path: a write that 403s would still
            # confirm the ticket is there.
            return Response(
                {"msg": "Ticket not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = TicketReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = request.FILES.getlist("files")

        try:
            with stored_attachments(files) as attachments:
                lifecycle.add_user_reply(
                    ticket=ticket,
                    user=request.user,
                    body=serializer.validated_data["body"],
                    attachments=attachments,
                )
        except lifecycle.TicketGone:
            # Deleted while the attachments were uploading. Same answer as if
            # it had already been gone when the request arrived, and the
            # context manager has taken the blobs back out on the way through.
            return Response(
                {"msg": "Ticket not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )
        ticket.refresh_from_db()
        return Response(
            {"msg": "Reply added successfully", "data": _detail_payload(ticket)},
            status=status.HTTP_201_CREATED,
        )


class TicketAttachmentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id, attachment_id):
        # Attachment ids are sequential and therefore guessable, so ownership
        # and the internal-note exclusion are conditions on the lookup rather
        # than checks afterwards. This queryset is the whole access control.
        attachment = (
            TicketAttachment.objects.filter(
                pk=attachment_id,
                message__ticket_id=ticket_id,
                message__ticket__created_by=request.user,
                message__ticket__deleted_at__isnull=True,
                message__deleted_at__isnull=True,
            )
            .exclude(message__message_type=TicketMessageType.INTERNAL_NOTE)
            .first()
        )
        if attachment is None:
            return Response(
                {"msg": "Attachment not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )
        return serve_managed_file(
            resolve_url=ticket_files.resolve_url,
            open_file=ticket_files.open,
            storage_key=attachment.storage_key,
            filename=attachment.original_filename,
            mime_type=attachment.mime_type,
            size=attachment.size,
            as_attachment=True,
        )
