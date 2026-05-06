# Phase 2 update: updated views to use new message lifecycle fields.
# Changes: deleted_flag=False → deleted_at__isnull=True in queryset filters,
# destroy() now calls soft_delete() instead of setting deleted_flag,
# added partial_update() for editing messages which sets edited_at automatically,
# updated WebSocket broadcast payloads to use new field names.

from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.http import FileResponse, HttpResponseRedirect
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .contracts import build_chat_message_payload, build_reaction_summary
from .management.permissions import CanModerateMessage, IsGroupMemberOrAdmin
from .models import MessageAttachment, MessageReaction, Messages
from .serializers import (
    MessageAttachmentUploadSerializer,
    MessageReactionToggleSerializer,
    MessageSerializer,
    MessageUpdateSerializer,
)
from .services.storage import open_managed_chat_file, resolve_managed_chat_file_url


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsGroupMemberOrAdmin]
    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action == "destroy":
            return [CanModerateMessage()]
        return [IsGroupMemberOrAdmin()]

    def get_serializer_class(self):
        if self.action == "upload":
            return MessageAttachmentUploadSerializer
        if self.action == "react":
            return MessageReactionToggleSerializer
        if self.action == "partial_update":
            return MessageUpdateSerializer
        return MessageSerializer

    def _message_queryset(self):
        # Load the related chat state up front because the canonical message payload includes
        # attachments, resource links, reactions, and read receipts in one response.
        return (
            Messages.objects.filter(deleted_at__isnull=True)
            .select_related("sender_user")
            .prefetch_related("attachments", "resources__resource", "reactions", "statuses")
        )

    def get_queryset(self):
        gid = self.kwargs.get("group_pk")
        return self._message_queryset().filter(group_id=gid)

    def _serialize_message(self, message):
        message = self._message_queryset().get(pk=message.pk)
        return build_chat_message_payload(message, request=self.request)

    def _broadcast_payload(self, group_id, payload):
        channel_layer = get_channel_layer()
        # HTTP-created messages broadcast through the same group channel the websocket consumer
        # joins, so REST and socket-originated activity land in one live stream.
        async_to_sync(channel_layer.group_send)(
            f"group_{group_id}",
            {
                "type": "chat.message",
                "payload": payload,
            },
        )

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
        data = MessageSerializer(items, many=True, context={"request": request}).data
        next_after = items[0].id if items else None

        return Response(
            {"items": data, "next_after": next_after},
            status=status.HTTP_200_OK
        )

    # POST /chat/groups/{gid}/messages/
    def perform_create(self, serializer):
        gid = int(self.kwargs.get("group_pk"))
        msg = serializer.save(sender_user=self.request.user, group_id=gid)
        # Reuse the same event envelope as uploads so the frontend only needs one upsert path
        # for persisted chat messages regardless of how they were created.
        payload = {
            "event": "message.created",
            "group_id": gid,
            "conversation_id": gid,
            "message": self._serialize_message(msg),
        }
        self._broadcast_payload(gid, payload)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(self._serialize_message(serializer.instance), status=status.HTTP_201_CREATED, headers=headers)

    @action(
        detail=False,
        methods=["post"],
        url_path="upload",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gid = int(self.kwargs.get("group_pk"))
        message = serializer.save(sender_user=request.user, group_id=gid)
        payload = {
            "event": "message.created",
            "group_id": gid,
            "conversation_id": gid,
            "message": self._serialize_message(message),
        }
        self._broadcast_payload(gid, payload)
        return Response(payload["message"], status=status.HTTP_201_CREATED)

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
                "conversation_id": instance.group_id,
                "message_id": instance.id,
                "message_text": instance.message_text,
                "edited_at": instance.edited_at.isoformat() if instance.edited_at else None,
            },
        )
        return Response(self._serialize_message(instance))

    # DELETE /chat/groups/{gid}/messages/{id}/
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()

        self._broadcast_payload(
            instance.group_id,
            {
                "event": "message.deleted",
                "group_id": instance.group_id,
                "conversation_id": instance.group_id,
                "message_id": instance.id,
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="react")
    def react(self, request, *args, **kwargs):
        message = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        emoji_string = serializer.validated_data["emoji_string"]

        # The frontend treats reactions as a toggle per emoji, so repeated clicks from the same
        # user add/remove the same row instead of creating duplicate reaction state.
        reaction, created = MessageReaction.objects.get_or_create(
            message=message,
            user=request.user,
            emoji_string=emoji_string,
        )
        if not created:
            reaction.delete()

        message = self._message_queryset().get(pk=message.pk)
        payload = {
            "type": "message.reaction_updated",
            "group_id": message.group_id,
            "conversation_id": message.group_id,
            "message_id": message.id,
            "emoji_string": emoji_string,
            # Broadcast the authoritative aggregate map after the toggle so every client can
            # reconcile its local reaction chips without reloading the whole message.
            "reactions": build_reaction_summary(message),
            "updated_by": request.user.id,
        }
        self._broadcast_payload(message.group_id, payload)
        return Response(
            {
                **payload,
                "toggled_on": created,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path=r"attachments/(?P<attachment_pk>\d+)/download",
        url_name="attachment-download",
    )
    def attachment_download(self, request, *args, **kwargs):
        message = self.get_object()
        attachment_pk = kwargs.get("attachment_pk")
        try:
            attachment = message.attachments.get(pk=attachment_pk)
        except MessageAttachment.DoesNotExist:
            return Response({"detail": "Attachment not found for this message."}, status=status.HTTP_404_NOT_FOUND)

        managed_url = resolve_managed_chat_file_url(
            attachment.storage_key,
            filename=attachment.attachment_filename,
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

        response = FileResponse(file_handle, as_attachment=True, filename=attachment.attachment_filename)
        if attachment.attachment_mime_type:
            response["Content-Type"] = attachment.attachment_mime_type
        if attachment.attachment_size is not None:
            response["Content-Length"] = str(attachment.attachment_size)
        return response
