"""The five endpoints a requester can reach.

Everything here answers 404 rather than 403 when someone asks about a ticket
that is not theirs. A 403 confirms the ticket exists, which is enough to walk
the id space and learn how many enquiries the platform has.
"""

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.storage import serve_managed_file

from .models import Ticket, TicketAttachment, TicketMessage, TicketMessageType
from .serializers import TicketCreateSerializer, TicketReplySerializer
from .services import lifecycle
from .services.attachments import stored_attachments, ticket_files

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

# What the requester is told a support reply came from. A role, not a person:
# the platform's users are minors, and nothing in the design asks for staff to
# be named to them.
SUPPORT_AUTHOR_LABEL = "Support"


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
    # much gets less, not an error.
    return page, min(limit, MAX_PAGE_SIZE)


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
    # Deliberately no priority and no assignee. The requester has no view of
    # either, and publishing them here would hand back through the API the
    # same information the two-clock rule keeps out of the timestamps.
    return {
        "id": ticket.pk,
        "ticketNumber": ticket.ticket_number,
        "subject": ticket.subject,
        "body": ticket.body,
        "category": ticket.category,
        "status": ticket.status,
        "createdAt": ticket.created_at,
        "lastUpdated": ticket.updated_at,
        "messages": [_message_payload(m) for m in _visible_messages(ticket)],
    }


class TicketListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page, limit = _page_params(request)
        offset = (page - 1) * limit
        queryset = _my_tickets(request.user).order_by("-updated_at")
        total = queryset.count()
        rows = [_list_row(t) for t in queryset[offset:offset + limit]]
        return Response({
            "msg": "Tickets retrieved successfully",
            "data": {
                "items": rows,
                "total": total,
                "page": page,
                "limit": limit,
                "hasMore": offset + len(rows) < total,
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

        with stored_attachments(files) as attachments:
            lifecycle.add_user_reply(
                ticket=ticket,
                user=request.user,
                body=serializer.validated_data["body"],
                attachments=attachments,
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
