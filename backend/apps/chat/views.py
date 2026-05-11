from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.storage import serve_managed_file
from .management.permissions import (
    CanEditMessage,
    CanModerateMessage,
    IsGroupMemberOrAdmin,
)
from .models import Messages
from .og_extractor import extract_urls
from .serializers import MessageSerializer, MessageUpdateSerializer
from .tasks import fetch_og_data
from .rbac import can_access_chat_group
from .models import MessageAttachment, Messages
from .serializers import (
    MessageAttachmentUploadSerializer,
    MessagePublicSerializer,
    MessageSerializer,
    MessageUpdateSerializer,
)
from .services.storage import CHAT_FILE_SERVICE, stored_chat_file
from apps.groups.models import Groups


def _broadcast(group_id: int, event: str, message_payload: dict) -> None:
    """Fan a chat event out to every consumer subscribed to ``group_id``.

    Wrapped in ``transaction.on_commit`` so a rolled-back DB write never
    produces a phantom WebSocket event. Envelope shape is the single
    contract documented at the top of
    ``apps/chat/management/consumers.py``.
    """
    channel_layer = get_channel_layer()
    envelope = {
        "type": "chat.message",
        "payload": {
            "event": event,
            "group_id": group_id,
            "message": message_payload,
        },
    }

    def _send():
        async_to_sync(channel_layer.group_send)(f"group_{group_id}", envelope)

    transaction.on_commit(_send)


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsGroupMemberOrAdmin]
    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAuthenticated(), CanModerateMessage()]
        if self.action == "partial_update":
            # Edit and delete share the same window-bounded RBAC rule, but the
            # permission classes stay split so view wiring expresses intent.
            return [IsAuthenticated(), CanEditMessage()]
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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["group_pk"] = self.kwargs.get("group_pk")
        return context

    def _serialize_public_message(self, message):
        # Re-fetch only when the prefetch cache is missing. The standard
        # queryset filters out soft-deleted rows, so for soft-deleted messages
        # we keep the raw instance. ``get_object()``-derived instances already
        # have attachments+resources prefetched.
        cache = getattr(message, "_prefetched_objects_cache", None) or {}
        if "attachments" not in cache or "resources" not in cache:
            try:
                message = self._message_queryset().get(pk=message.pk)
            except Messages.DoesNotExist:
                pass
        return MessagePublicSerializer(message, context=self.get_serializer_context()).data

    def _serialize_broadcast_message(self, message):
        # Re-fetch only when the prefetch cache is empty — get_object()-derived
        # instances (partial_update, destroy) already have attachments+resources
        # prefetched, so the broadcast doesn't need to round-trip the DB. Freshly
        # created instances from serializer.save() do need the fetch.
        cache = getattr(message, "_prefetched_objects_cache", None) or {}
        if "attachments" not in cache or "resources" not in cache:
            try:
                message = (
                    Messages.objects.select_related("sender_user")
                    .prefetch_related("attachments", "resources__resource")
                    .get(pk=message.pk)
                )
            except Messages.DoesNotExist:
                pass

        context = self.get_serializer_context()
        data = MessageSerializer(message, context=context).data
        # MessageSerializer's nested attachments lack download_url; rebuild from
        # the public shape that does include it.
        data["attachments"] = MessagePublicSerializer(message, context=context).data.get("attachments", [])
        # Legacy aliases kept for the existing frontend / tests; preserved
        # alongside MessageSerializer's canonical fields so both new and old
        # clients can read the same payload without a protocol migration.
        # ``message.resources.all()`` walks the prefetch cache instead of issuing
        # a fresh query.
        data["sender_id"] = message.sender_user_id
        data["text"] = data.get("message_text", "")
        data["resource_ids"] = [r.resource_id for r in message.resources.all()]
        return data

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
        data = MessagePublicSerializer(items, many=True, context=self.get_serializer_context()).data
        next_after = items[0].id if items else None

        return Response(
            {"items": data, "next_after": next_after},
            status=status.HTTP_200_OK,
        )

    # POST /chat/groups/{gid}/messages/
    def perform_create(self, serializer):
        gid = int(self.kwargs.get("group_pk"))
        msg = serializer.save(sender_user=self.request.user, group_id=gid)
        _broadcast(gid, "message.created", MessageSerializer(msg).data)
        self._dispatch_link_previews(msg)

    def _dispatch_link_previews(self, message: Messages) -> None:
        """Fire-and-forget OG unfurl for every URL in the message body.

        We do NOT block the HTTP response on this — the user gets ``201``
        immediately and the websocket later carries ``message.preview_ready``
        per the worker contract documented in ``apps.chat.tasks``.

        The dispatch is wrapped in ``transaction.on_commit`` for two reasons:

        1. If the surrounding DB write is rolled back (e.g. permissions
           check fails late, signal raises), no orphan task can hit a
           non-existent message id.
        2. Eager Celery execution (used in unit tests) would otherwise run
           inside the request transaction and read its own pre-commit row,
           which doesn't model production behaviour.
        """
        urls = extract_urls(message.message_text)
        if not urls:
            return
        msg_id = message.id

        def _enqueue():
            for url in urls:
                fetch_og_data.delay(msg_id, url)

        transaction.on_commit(_enqueue)

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
        uploaded_file = serializer.validated_data["uploaded_file"]
        gid = group.id

        # stored_chat_file wraps the blob upload so any exception inside the
        # atomic block — DB write, broadcast, serialization — deletes the blob
        # before propagating, leaving no orphaned file behind on rollback.
        with stored_chat_file(uploaded_file) as attachment_data:
            serializer.context["attachment_data"] = attachment_data
            with transaction.atomic():
                message = serializer.save(sender_user=request.user, group_id=gid)
                # _broadcast itself wraps in transaction.on_commit, so a rollback
                # of this atomic block discards the WS event automatically.
                _broadcast(gid, "message.created", self._serialize_broadcast_message(message))
        return Response(self._serialize_public_message(message), status=status.HTTP_201_CREATED)

    # PATCH /chat/groups/{gid}/messages/{id}/
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        _broadcast(
            instance.group_id, "message.edited", self._serialize_broadcast_message(instance)
        )
        return Response(self._serialize_public_message(instance))

    # DELETE /chat/groups/{gid}/messages/{id}/
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()

        _broadcast(
            instance.group_id, "message.deleted", self._serialize_broadcast_message(instance)
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

        return serve_managed_file(
            resolve_url=CHAT_FILE_SERVICE.resolve_url,
            open_file=CHAT_FILE_SERVICE.open,
            storage_key=attachment.storage_key,
            filename=attachment.attachment_filename,
            mime_type=attachment.attachment_mime_type,
            size=attachment.attachment_size,
            as_attachment=True,
            on_open_failure_detail="The attachment could not be opened for download.",
        )
