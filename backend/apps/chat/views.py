# Phase 2 update: updated views to use new message lifecycle fields.
# Changes: deleted_flag=False → deleted_at__isnull=True in queryset filters,
# destroy() now calls soft_delete() instead of setting deleted_flag,
# added partial_update() for editing messages which sets edited_at automatically,
# updated WebSocket broadcast payloads to use new field names.

from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.http import FileResponse, HttpResponseRedirect
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.filenames import sanitize_upload_filename
from .management.permissions import CanModerateMessage, IsGroupMemberOrAdmin
from .rbac import can_access_chat_group
from .models import MessageAttachment, Messages
from .serializers import (
    MessageAttachmentUploadSerializer,
    MessagePublicSerializer,
    MessageSerializer,
    MessageUpdateSerializer,
)
from .services.storage import open_managed_chat_file, resolve_managed_chat_file_url
from apps.groups.models import Groups


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsGroupMemberOrAdmin]
    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAuthenticated(), CanModerateMessage()]
        if self.action in {"upload", "attachment_download"}:
            return [IsAuthenticated()]
        return [IsGroupMemberOrAdmin()]

    def get_serializer_class(self):
        if self.action == "upload":
            return MessageAttachmentUploadSerializer
        if self.action == "partial_update":
            return MessageUpdateSerializer
        if self.action == "retrieve":
            return MessagePublicSerializer
        return MessageSerializer

    def _message_queryset(self):
        return (
            Messages.objects.filter(deleted_at__isnull=True)
            .select_related("sender_user")
            .prefetch_related("attachments", "resources__resource")
        )

    def get_queryset(self):
        gid = self.kwargs.get("group_pk")
        return self._message_queryset().filter(group_id=gid)

    def _serialize_public_message(self, message):
        message = self._message_queryset().get(pk=message.pk)
        return MessagePublicSerializer(message, context={"request": self.request}).data

    def _serialize_broadcast_message(self, message):
        message = self._message_queryset().get(pk=message.pk)
        data = MessagePublicSerializer(message, context={"request": self.request}).data
        # Keep legacy aliases in websocket payloads so the existing frontend and tests
        # continue to understand message.created without a protocol migration.
        data["sender_id"] = message.sender_user_id
        data["text"] = data.get("message_text", "")
        data["resource_ids"] = list(message.resources.values_list("resource_id", flat=True))
        return data

    def _broadcast_payload(self, group_id, payload):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"group_{group_id}",
            {
                "type": "chat.message",
                "payload": payload,
            },
        )

    def _build_message_created_payload(self, group_id, message):
        return {
            "event": "message.created",
            "group_id": group_id,
            "message": self._serialize_broadcast_message(message),
        }

    def _get_group(self):
        group_pk = self.kwargs.get("group_pk")
        return Groups.objects.only("id", "track_id").filter(pk=group_pk).first()

    # GET /chat/groups/{gid}/messages/
    def list(self, request, *args, **kwargs):
        gid = self.kwargs.get("group_pk")
        qs = self.get_queryset().order_by("-sent_at", "-id")

        after = request.query_params.get("after")
        if after:
            try:
                pivot = Messages.objects.get(pk=int(after), group_id=gid)
                qs = qs.filter(
                    Q(sent_at__gt=pivot.sent_at)
                    | Q(sent_at=pivot.sent_at, id__gt=pivot.id)
                )
            except (ValueError, Messages.DoesNotExist):
                pass

        try:
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 100))

        items = list(qs[:limit])
        data = MessagePublicSerializer(items, many=True, context={"request": request}).data
        next_after = items[0].id if items else None

        return Response(
            {"items": data, "next_after": next_after},
            status=status.HTTP_200_OK
        )

    # POST /chat/groups/{gid}/messages/
    def perform_create(self, serializer):
        gid = int(self.kwargs.get("group_pk"))
        msg = serializer.save(sender_user=self.request.user, group_id=gid)
        payload = self._build_message_created_payload(gid, msg)
        self._broadcast_payload(gid, payload)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(self._serialize_public_message(serializer.instance), status=status.HTTP_201_CREATED, headers=headers)

    @action(
        detail=False,
        methods=["post"],
        url_path="upload",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload(self, request, *args, **kwargs):
        group = self._get_group()
        if group is None:
            return Response({"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_access_chat_group(request.user, group):
            return Response({"detail": "You do not have access to this group."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gid = group.id
        with transaction.atomic():
            message = serializer.save(sender_user=request.user, group_id=gid)
            payload = self._build_message_created_payload(gid, message)
            # Developer note: upload writes the message + attachment first, then publishes
            # on commit so websocket consumers never receive an attachment event for rows
            # that later roll back.
            transaction.on_commit(
                lambda group_id=gid, message_payload=payload: self._broadcast_payload(
                    group_id,
                    message_payload,
                )
            )
        return Response(self._serialize_public_message(message), status=status.HTTP_201_CREATED)

    # PATCH /chat/groups/{gid}/messages/{id}/
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self._broadcast_payload(
            instance.group_id,
            {
                "event": "message.edited",
                "group_id": instance.group_id,
                "message_id": instance.id,
                "message_text": instance.message_text,
                "edited_at": instance.edited_at.isoformat() if instance.edited_at else None,
            },
        )
        return Response(self._serialize_public_message(instance))

    # DELETE /chat/groups/{gid}/messages/{id}/
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()

        self._broadcast_payload(
            instance.group_id,
            {
                "event": "message.deleted",
                "group_id": instance.group_id,
                "message_id": instance.id,
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["get"],
        url_path=r"attachments/(?P<attachment_pk>\d+)/download",
        url_name="attachment-download",
    )
    def attachment_download(self, request, *args, **kwargs):
        group = self._get_group()
        if group is None:
            return Response({"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND)

        message = self.get_object()
        attachment_pk = kwargs.get("attachment_pk")
        attachment = message.attachments.filter(pk=attachment_pk).first()
        if attachment is None:
            return Response({"detail": "Attachment not found for this message."}, status=status.HTTP_404_NOT_FOUND)

        if not can_access_chat_group(request.user, group):
            return Response({"detail": "You do not have access to this group."}, status=status.HTTP_403_FORBIDDEN)

        safe_filename = sanitize_upload_filename(attachment.attachment_filename)
        managed_url = resolve_managed_chat_file_url(
            attachment.storage_key,
            filename=safe_filename,
            content_type=attachment.attachment_mime_type,
            as_attachment=True,
        )
        # Prefer redirecting to a signed Blob URL in production; local/test storage falls
        # back to Django streaming below.
        if managed_url:
            parsed_url = urlparse(managed_url)
            if parsed_url.scheme and parsed_url.netloc:
                return HttpResponseRedirect(managed_url)

        try:
            file_handle = open_managed_chat_file(attachment.storage_key)
        except Exception:
            return Response({"detail": "The attachment could not be opened for download."}, status=status.HTTP_404_NOT_FOUND)

        response = FileResponse(file_handle, as_attachment=True, filename=safe_filename)
        if attachment.attachment_mime_type:
            response["Content-Type"] = attachment.attachment_mime_type
        if attachment.attachment_size is not None:
            response["Content-Length"] = str(attachment.attachment_size)
        return response
