from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from groups.models import Group

from .models import Message
from .permissions import user_can_moderate_group_chat, user_has_group_access
from .serializers import MessageSerializer
from .services import broadcast_message_event, create_message, serialize_message


class MessageViewSet(viewsets.ViewSet):
    """
    Provides listing and creation of chat messages scoped to a group.
    """

    permission_classes = [IsAuthenticated]
    max_page_size = 100
    default_page_size = 50

    def list(self, request, group_id: str) -> Response:
        group = self._get_group_or_403(group_id, request.user)
        queryset = (
            Message.objects.filter(group=group)
            .select_related("author", "deleted_by", "moderated_by")
            .prefetch_related("attachments")
            .order_by("-created_at", "-id")
        )

        can_moderate = user_can_moderate_group_chat(request.user, group)
        if not can_moderate:
            queryset = queryset.filter(is_deleted=False).exclude(
                moderation_status=Message.ModerationStatus.REJECTED
            )

        before_param = request.query_params.get("before")
        if before_param:
            before_dt = parse_datetime(before_param)
            if before_dt is None:
                raise ValidationError({"before": "Invalid datetime format."})
            if timezone.is_naive(before_dt):
                before_dt = timezone.make_aware(before_dt, timezone=timezone.utc)
            queryset = queryset.filter(created_at__lt=before_dt)

        limit = request.query_params.get("limit")
        try:
            page_size = int(limit) if limit is not None else self.default_page_size
        except (TypeError, ValueError):
            raise ValidationError({"limit": "Limit must be an integer."})
        page_size = max(1, min(page_size, self.max_page_size))

        messages = list(queryset[: page_size + 1])
        has_more = len(messages) > page_size
        messages = messages[:page_size]

        serializer = MessageSerializer(messages, many=True, context={"user": request.user})
        return Response(
            {
                "messages": serializer.data,
                "hasMore": has_more,
            },
            status=status.HTTP_200_OK,
        )

    def create(self, request, group_id: str) -> Response:
        group = self._get_group_or_403(group_id, request.user)

        text = request.data.get("text", "")
        attachments_payload = request.data.get("attachments") or []

        message = create_message(group, request.user, text, attachments_payload)

        response_serializer = MessageSerializer(message, context={"user": request.user})

        broadcast_message_event(
            str(group.pk),
            "message.created",
            serialize_message(message, for_user=None),
        )

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, group_id: str, pk: str | None = None) -> Response:
        group = self._get_group_or_403(group_id, request.user)
        message = self._get_message_or_404(group, pk)

        if not user_can_moderate_group_chat(request.user, group):
            raise PermissionDenied("You do not have permission to moderate messages.")

        moderation_status = request.data.get("moderationStatus")
        moderation_note = request.data.get("moderationNote")
        restore_flag = request.data.get("restore")

        updates: list[str] = []

        if moderation_status is not None:
            if moderation_status not in Message.ModerationStatus.values:
                raise ValidationError({"moderationStatus": "Invalid moderation status."})
            message.moderation_status = moderation_status
            message.moderated_at = timezone.now()
            message.moderated_by = request.user
            updates.extend(["moderation_status", "moderated_at", "moderated_by"])

        if moderation_note is not None:
            message.moderation_note = str(moderation_note or "").strip()
            updates.append("moderation_note")

        if restore_flag:
            message.is_deleted = False
            message.deleted_at = None
            message.deleted_by = None
            updates.extend(["is_deleted", "deleted_at", "deleted_by"])

        if not updates:
            raise ValidationError("No valid fields provided for update.")

        message.save(update_fields=list(set(updates)))
        message.refresh_from_db()

        response_serializer = MessageSerializer(message, context={"user": request.user})
        broadcast_message_event(
            str(group.pk),
            "message.updated",
            serialize_message(message, for_user=None),
        )

        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, group_id: str, pk: str | None = None) -> Response:
        group = self._get_group_or_403(group_id, request.user)
        message = self._get_message_or_404(group, pk)

        if not user_can_moderate_group_chat(request.user, group):
            raise PermissionDenied("You do not have permission to delete messages.")

        if not message.is_deleted:
            message.is_deleted = True
            message.deleted_at = timezone.now()
            message.deleted_by = request.user
            message.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

        message.refresh_from_db()

        serializer = MessageSerializer(message, context={"user": request.user})
        broadcast_message_event(
            str(group.pk),
            "message.deleted",
            serialize_message(message, for_user=None),
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def _get_group_or_403(self, group_id: str, user) -> Group:
        group = get_object_or_404(Group.objects.select_related("mentor"), pk=group_id)
        if not user_has_group_access(user, group):
            raise PermissionDenied("You do not have access to this group.")
        return group

    def _get_message_or_404(self, group: Group, pk: str | None) -> Message:
        if pk is None:
            raise ValidationError({"id": "Message id is required."})
        return get_object_or_404(
            Message.objects.select_related("author", "deleted_by", "moderated_by").prefetch_related("attachments"),
            pk=pk,
            group=group,
        )
