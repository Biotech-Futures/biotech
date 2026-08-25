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
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin.permissions import IsAdminScoped
from apps.audit.models import AuditLog
from apps.audit.services import log_audit_event
from apps.common.storage import serve_managed_file

from .models import (
    SupportScope,
    Ticket,
    TicketAttachment,
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
from .services import lifecycle
from .services.attachments import stored_attachments, ticket_files
from .services.queue import (
    apply_filters,
    known_regions,
    live_tickets,
    overdue_ids,
    summary,
    support_capable_users,
)
from .views import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, _page_params

User = get_user_model()

SUPPORT_PERMISSIONS = [IsAuthenticated, IsSupportScoped]


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
            # Derived, not stored. Anonymous submission was never built, so
            # the only tickets with no requester are the ones screening
            # raises — and those must not show up in the queue labelled as
            # anonymous submissions.
            "anonymous": ticket.created_by_id is None and ticket.channel != "ai_screening",
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
        offset = (page - 1) * limit
        queryset = apply_filters(
            live_tickets().select_related("created_by", "assignee"),
            region=request.query_params.get("region"),
            status=request.query_params.get("status"),
            category=request.query_params.get("category"),
            assignee=request.query_params.get("assignee"),
            priority=request.query_params.get("priority"),
            search=request.query_params.get("search"),
        ).order_by("-support_updated_at")

        total = queryset.count()
        tickets = list(queryset[offset:offset + limit])
        flagged = overdue_ids(tickets)
        rows = [_queue_row(t, overdue=t.pk in flagged) for t in tickets]
        return Response({
            "msg": "Ticket queue retrieved successfully",
            "data": {
                "items": rows,
                "total": total,
                "page": page,
                "limit": limit,
                "hasMore": offset + len(rows) < total,
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
        return Response({
            "msg": "Assignees retrieved successfully",
            "data": [_person(user) for user in support_capable_users()],
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

        # Priority first and on its own terms: it is invisible to the
        # requester, so it moves the support clock only and writes no timeline
        # message.
        if "priority" in changes:
            before = ticket.priority
            after = changes["priority"]
            if before != after:
                log_audit_event(
                    actor=request.user,
                    entity_type=lifecycle.AUDIT_ENTITY_TYPE,
                    entity_id=ticket.pk,
                    action="priority",
                    before_state={"priority": before},
                    after_state={"priority": after},
                )
                lifecycle._touch(ticket, user_visible=False, priority=after)

        if "status" in changes:
            lifecycle.set_status(
                ticket=ticket, new_status=changes["status"], actor=request.user
            )
        elif "assignee" in changes:
            lifecycle.assign(
                ticket=ticket, actor=request.user, assignee=changes["assignee"]
            )

        ticket.refresh_from_db()
        return Response({
            "msg": "Ticket updated successfully",
            "data": _detail(ticket, overdue=ticket.pk in overdue_ids([ticket])),
        })


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


class TicketSupportMessageView(APIView):
    permission_classes = SUPPORT_PERMISSIONS

    def post(self, request, ticket_id):
        ticket = _get_ticket_or_none(ticket_id)
        if ticket is None:
            return _not_found()

        serializer = SupportMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message_type = serializer.validated_data["messageType"]
        body = serializer.validated_data["body"]
        files = request.FILES.getlist("files")

        with stored_attachments(files) as attachments:
            if message_type == TicketMessageType.INTERNAL_NOTE:
                lifecycle.add_internal_note(
                    ticket=ticket, actor=request.user, body=body, attachments=attachments
                )
            else:
                lifecycle.add_support_reply(
                    ticket=ticket, actor=request.user, body=body, attachments=attachments
                )

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


class SupportScopeView(APIView):
    """Who is on the support roster.

    Admins only. Every admin can already work the queue, so this is about
    granting the role to someone who is not an admin — the client will ask
    "how do I add a support person?" at handover, and "insert a row with the
    Django shell" is not an answer.
    """

    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        rows = SupportScope.objects.select_related("user").order_by("user__first_name")
        return Response({
            "msg": "Support roster retrieved successfully",
            "data": [
                {**_person(row.user), "email": row.user.email} for row in rows
            ],
        })

    def post(self, request):
        serializer = SupportScopeGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(pk=serializer.validated_data["userId"]).first()
        if user is None:
            return _not_found("User")

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
