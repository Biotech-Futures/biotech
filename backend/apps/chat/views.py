from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.common.storage import serve_managed_file
from apps.groups.models import Groups

from .management.permissions import (
    CanEditMessage,
    CanModerateMessage,
    IsGroupMemberOrAdmin,
)
from .models import Messages
from .og_extractor import extract_urls
from .serializers import (
    MessageAttachmentUploadSerializer,
    MessagePublicSerializer,
    MessageSerializer,
    MessageUpdateSerializer,
)
from .services.storage import CHAT_FILE_SERVICE, stored_chat_file
from .tasks import dispatch_og


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

    def get_permissions(self):
        if self.action == "destroy":
            return [CanModerateMessage()]
        if self.action == "partial_update":
            return [CanEditMessage()]
        return [IsGroupMemberOrAdmin()]

    def get_serializer_class(self):
        if self.action == "partial_update":
            return MessageUpdateSerializer
        if self.action == "upload":
            return MessageAttachmentUploadSerializer
        return MessageSerializer

    def _message_queryset(self):
        # ``reply_to`` is select_related so the embedded parent context
        # does not issue an extra query per row. The join is intentionally
        # one level deep — mirroring ReplyToSerializer's bounded shape —
        # so a long chain of quotes still costs exactly one extra JOIN.
        return (
            Messages.objects.filter(deleted_at__isnull=True)
            .select_related("sender_user", "reply_to")
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
                    Messages.objects.select_related("sender_user", "reply_to")
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
        # Public shape — caller never sees the internal `group` / `sender_user`
        # FK fields, which match the contract documented in tests/_helpers.py.
        data = MessagePublicSerializer(
            items, many=True, context=self.get_serializer_context()
        ).data
        next_after = items[0].id if items else None

        return Response(
            {"items": data, "next_after": next_after},
            status=status.HTTP_200_OK,
        )

    # POST /chat/groups/{gid}/messages/
    def perform_create(self, serializer):
        gid = int(self.kwargs.get("group_pk"))
        msg = serializer.save(sender_user=self.request.user, group_id=gid)
        _broadcast(gid, "message.created", self._serialize_broadcast_message(msg))
        self._dispatch_link_previews(msg)
        # Stash the saved instance so ``create()`` can render the public shape
        # without re-running the input serializer.
        self._created_message = msg

    def _dispatch_link_previews(self, message: Messages) -> None:
        """Fire-and-forget OG unfurl for every URL in the message body.

        We do NOT block the HTTP response on this — the user gets ``201``
        immediately and the websocket later carries ``message.preview_ready``
        per the worker contract documented in ``apps.chat.tasks``.

        Why ``transaction.on_commit``:

        1. If the surrounding DB write is rolled back (e.g. permissions
           check fails late, signal raises), the unfurl never starts and
           cannot hit a non-existent message id.
        2. The worker thread opens its own DB connection — it must read a
           **committed** row, otherwise it sees nothing.
        """
        urls = extract_urls(message.message_text)
        if not urls:
            return
        msg_id = message.id

        def _enqueue():
            for url in urls:
                dispatch_og(msg_id, url)

        transaction.on_commit(_enqueue)

    def create(self, request, *args, **kwargs):
        # Use MessageSerializer for input validation (it knows about resources,
        # reply_to, sanitisation rules), then render the public shape on the
        # way out. This keeps the public contract free of internal FK fields.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        public = self._serialize_public_message(self._created_message)
        return Response(public, status=status.HTTP_201_CREATED)

    # PATCH /chat/groups/{gid}/messages/{id}/
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        _broadcast(
            instance.group_id,
            "message.edited",
            self._serialize_broadcast_message(instance),
        )
        return Response(self._serialize_public_message(instance))

    # DELETE /chat/groups/{gid}/messages/{id}/
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        _broadcast(
            instance.group_id,
            "message.deleted",
            self._serialize_broadcast_message(instance),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # POST /chat/groups/{gid}/messages/upload/
    @action(
        detail=False,
        methods=["post"],
        url_path="upload",
        url_name="upload",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload(self, request, *args, **kwargs):
        """Create an attachment-type message in one round trip.

        Flow:

        1. Validate the multipart payload (size / extension / MIME) before
           touching storage — invalid uploads return 400 with no blob written.
        2. Stream the file to managed storage. ``stored_chat_file`` is a
           context manager that deletes the blob if anything later in the
           ``with`` block raises, so a failed DB write or broadcast can't
           leave orphaned bytes.
        3. Inside ``transaction.atomic``, persist the Messages row + the
           MessageAttachment row, then enqueue a ``message.created`` WS
           broadcast (deferred until commit by ``_broadcast``). Any error
           rolls back both DB rows AND triggers blob cleanup.
        """
        gid = int(self.kwargs["group_pk"])
        serializer = MessageAttachmentUploadSerializer(
            data=request.data,
            context={"group_pk": gid, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["uploaded_file"]

        with stored_chat_file(uploaded_file) as attachment_data:
            with transaction.atomic():
                serializer.context["attachment_data"] = attachment_data
                message = serializer.save(
                    sender_user=request.user,
                    group_id=gid,
                )
                _broadcast(
                    gid,
                    "message.created",
                    self._serialize_broadcast_message(message),
                )
                # Attachment captions can carry URLs too — keep unfurl behavior
                # uniform with the plain-text POST path. Dispatch is on_commit,
                # so a failed transaction still cleans up cleanly.
                self._dispatch_link_previews(message)

        return Response(
            self._serialize_public_message(message),
            status=status.HTTP_201_CREATED,
        )

    # GET /chat/groups/{gid}/messages/{pk}/attachments/{attachment_pk}/download/
    @action(
        detail=True,
        methods=["get"],
        url_path=r"attachments/(?P<attachment_pk>\d+)/download",
        url_name="attachment-download",
    )
    def attachment_download(self, request, *args, attachment_pk=None, **kwargs):
        # ``get_object()`` runs ``get_queryset()`` which already restricts to
        # the current group + non-soft-deleted messages, so a mismatched
        # message / group pair naturally returns 404 instead of leaking the
        # existence of the row in another group.
        message = self.get_object()
        attachment = message.attachments.filter(pk=attachment_pk).first()
        if attachment is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return serve_managed_file(
            resolve_url=CHAT_FILE_SERVICE.resolve_url,
            open_file=CHAT_FILE_SERVICE.open,
            storage_key=attachment.storage_key,
            filename=attachment.attachment_filename,
            mime_type=attachment.attachment_mime_type,
            size=attachment.attachment_size,
            as_attachment=True,
        )
