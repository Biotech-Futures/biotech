from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.utils import timezone
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
from .rbac import can_access_chat_group
from .models import MessageAttachment, MessageReaction, MessageStatus, Messages
from .serializers import (
    MessageAttachmentUploadSerializer,
    MessagePublicSerializer,
    MessageSerializer,
    MessageUpdateSerializer,
    aggregate_reactions,
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


def _broadcast_read(group_id: int, reader_id: int, up_to_id: int) -> None:
    """Read-cursor updates carry only the reader and the cursor message.

    Clients interpret this as "user ``reader_id`` has read every message
    in this group with id <= ``up_to_id``". Flat envelope (no ``message``
    wrapper) with ``type`` duplicated alongside ``event`` so the FE can
    branch on ``payload.type``.
    """
    channel_layer = get_channel_layer()
    envelope = {
        "type": "chat.message",
        "payload": {
            "event": "message.read_updated",
            "type": "message.read_updated",
            "group_id": group_id,
            "reader_id": reader_id,
            "up_to_id": up_to_id,
        },
    }

    def _send():
        async_to_sync(channel_layer.group_send)(f"group_{group_id}", envelope)

    transaction.on_commit(_send)


def _broadcast_delivered(group_id: int, user_id: int, up_to_id: int) -> None:
    """Mirror of ``_broadcast_read`` for the delivered cursor.

    Same flat envelope shape; FE branches on ``payload.type``
    (``message.delivered_updated`` vs ``message.read_updated``).
    """
    channel_layer = get_channel_layer()
    envelope = {
        "type": "chat.message",
        "payload": {
            "event": "message.delivered_updated",
            "type": "message.delivered_updated",
            "group_id": group_id,
            "user_id": user_id,
            "up_to_id": up_to_id,
        },
    }

    def _send():
        async_to_sync(channel_layer.group_send)(f"group_{group_id}", envelope)

    transaction.on_commit(_send)


def _broadcast_reaction(group_id: int, message_id: int, reactions: dict) -> None:
    """Reaction updates use a flatter envelope than message events.

    Reactions don't need the full message payload — only the aggregated
    map. ``type`` is duplicated alongside ``event`` so clients reading
    either key (the FE currently reads ``payload.type``) stay in sync.
    """
    channel_layer = get_channel_layer()
    envelope = {
        "type": "chat.message",
        "payload": {
            "event": "message.reaction_updated",
            "type": "message.reaction_updated",
            "group_id": group_id,
            "message_id": message_id,
            "reactions": reactions,
        },
    }

    def _send():
        async_to_sync(channel_layer.group_send)(f"group_{group_id}", envelope)

    transaction.on_commit(_send)


def mark_delivered_cursor(user, group_id: int, up_to_id: int) -> int:
    """Mark every non-deleted message in ``group_id`` with ``id <= up_to_id``
    as delivered for ``user``, skipping ``user``'s own messages.

    Idempotent. Never downgrades a row that is already ``read`` — the
    filter on ``delivered_at__isnull=True`` excludes already-delivered
    rows (which includes every read row, since the read endpoint sets
    ``delivered_at`` alongside ``read_at``).

    Returns the size of the cursor scope. Matches the ``read`` action's
    ``marked_count`` semantics (scope size, not newly-changed-row count)
    so the two endpoints feel symmetric to the FE.
    """
    scope_ids = list(
        Messages.objects
        .filter(group_id=group_id, id__lte=up_to_id, deleted_at__isnull=True)
        .exclude(sender_user_id=user.id)
        .values_list("id", flat=True)
    )
    if not scope_ids:
        return 0

    now = timezone.now()
    DELIVERED = MessageStatus.StatusChoices.DELIVERED

    with transaction.atomic():
        existing_ids = set(
            MessageStatus.objects
            .filter(message_id__in=scope_ids, user=user)
            .values_list("message_id", flat=True)
        )
        to_create = [
            MessageStatus(
                message_id=mid,
                user=user,
                status=DELIVERED,
                delivered_at=now,
            )
            for mid in scope_ids if mid not in existing_ids
        ]
        if to_create:
            MessageStatus.objects.bulk_create(to_create, ignore_conflicts=True)

        # Backfill ``delivered_at`` on existing rows without overwriting a
        # set ``read_at``. Already-read rows have ``delivered_at`` set by
        # the read endpoint, so the ``delivered_at__isnull=True`` filter
        # excludes them. The split-by-``read_at`` form guards a paranoid
        # edge case (read_at set, delivered_at null) where we still want
        # to backfill delivered_at without DOWNGRADING ``status`` to
        # delivered.
        MessageStatus.objects.filter(
            message_id__in=existing_ids,
            user=user,
            delivered_at__isnull=True,
            read_at__isnull=True,
        ).update(status=DELIVERED, delivered_at=now)
        MessageStatus.objects.filter(
            message_id__in=existing_ids,
            user=user,
            delivered_at__isnull=True,
            read_at__isnull=False,
        ).update(delivered_at=now)

    _broadcast_delivered(group_id, user.id, up_to_id)
    return len(scope_ids)


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
        if self.action in {"read", "delivered", "react"}:
            return [IsAuthenticated(), IsGroupMemberOrAdmin()]
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
        # ``reply_to`` is select_related so the embedded parent context
        # does not issue an extra query per row. The join is intentionally
        # one level deep — mirroring ReplyToSerializer's bounded shape —
        # so a long chain of quotes still costs exactly one extra JOIN.
        user_id = getattr(getattr(self, "request", None), "user", None)
        user_id = getattr(user_id, "id", None)
        return (
            Messages.objects.filter(deleted_at__isnull=True)
            .select_related("sender_user", "reply_to")
            .prefetch_related(
                "attachments",
                "resources__resource",
                Prefetch(
                    "reactions",
                    queryset=MessageReaction.objects.select_related("user").order_by("id"),
                ),
            )
            .annotate(
                _read_count=Count(
                    "statuses",
                    filter=Q(statuses__read_at__isnull=False),
                    distinct=True,
                ),
                _delivered_count=Count(
                    "statuses",
                    filter=Q(statuses__delivered_at__isnull=False),
                    distinct=True,
                ),
                _is_read_by_me=Exists(
                    MessageStatus.objects.filter(
                        message=OuterRef("pk"),
                        user_id=user_id,
                        read_at__isnull=False,
                    )
                ),
                _is_delivered_to_me=Exists(
                    MessageStatus.objects.filter(
                        message=OuterRef("pk"),
                        user_id=user_id,
                        delivered_at__isnull=False,
                    )
                ),
            )
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
        # have attachments+resources+reactions prefetched.
        cache = getattr(message, "_prefetched_objects_cache", None) or {}
        if (
            "attachments" not in cache
            or "resources" not in cache
            or "reactions" not in cache
        ):
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
        if (
            "attachments" not in cache
            or "resources" not in cache
            or "reactions" not in cache
        ):
            user_id = getattr(getattr(self, "request", None), "user", None)
            user_id = getattr(user_id, "id", None)
            try:
                message = (
                    Messages.objects.select_related("sender_user", "reply_to")
                    .prefetch_related(
                        "attachments",
                        "resources__resource",
                        Prefetch(
                            "reactions",
                            queryset=MessageReaction.objects.select_related("user").order_by("id"),
                        ),
                    )
                    .annotate(
                        _read_count=Count(
                            "statuses",
                            filter=Q(statuses__read_at__isnull=False),
                            distinct=True,
                        ),
                        _delivered_count=Count(
                            "statuses",
                            filter=Q(statuses__delivered_at__isnull=False),
                            distinct=True,
                        ),
                        _is_read_by_me=Exists(
                            MessageStatus.objects.filter(
                                message=OuterRef("pk"),
                                user_id=user_id,
                                read_at__isnull=False,
                            )
                        ),
                        _is_delivered_to_me=Exists(
                            MessageStatus.objects.filter(
                                message=OuterRef("pk"),
                                user_id=user_id,
                                delivered_at__isnull=False,
                            )
                        ),
                    )
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
        _broadcast(gid, "message.created", self._serialize_broadcast_message(msg))

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

    @action(detail=True, methods=["post"], url_path="read")
    def read(self, request, *args, **kwargs):
        # Cursor semantics: mark this message AND all earlier messages in
        # the same group as read by the caller. Idempotent — re-marking
        # a read message is a no-op. The sender's own messages are
        # skipped (no MessageStatus row is created for them) so
        # ``read_count`` cleanly excludes the sender.
        target = self.get_object()
        gid = target.group_id

        scope_ids = list(
            Messages.objects
            .filter(group_id=gid, id__lte=target.id, deleted_at__isnull=True)
            .exclude(sender_user_id=request.user.id)
            .values_list("id", flat=True)
        )
        if not scope_ids:
            return Response({"marked_count": 0, "up_to_id": target.id}, status=status.HTTP_200_OK)

        now = timezone.now()
        READ = MessageStatus.StatusChoices.READ

        with transaction.atomic():
            existing_ids = set(
                MessageStatus.objects
                .filter(message_id__in=scope_ids, user=request.user)
                .values_list("message_id", flat=True)
            )
            to_create = [
                MessageStatus(
                    message_id=mid,
                    user=request.user,
                    status=READ,
                    delivered_at=now,
                    read_at=now,
                )
                for mid in scope_ids if mid not in existing_ids
            ]
            if to_create:
                MessageStatus.objects.bulk_create(to_create, ignore_conflicts=True)

            # Bring previously-unread existing rows up to ``read``. Two
            # filtered updates so we set ``delivered_at`` only when it's
            # null (a ``COALESCE`` in plain Django ORM update is awkward).
            MessageStatus.objects.filter(
                message_id__in=existing_ids,
                user=request.user,
                read_at__isnull=True,
                delivered_at__isnull=True,
            ).update(status=READ, read_at=now, delivered_at=now)
            MessageStatus.objects.filter(
                message_id__in=existing_ids,
                user=request.user,
                read_at__isnull=True,
                delivered_at__isnull=False,
            ).update(status=READ, read_at=now)

        _broadcast_read(gid, request.user.id, target.id)
        return Response(
            {"marked_count": len(scope_ids), "up_to_id": target.id},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="react")
    def react(self, request, *args, **kwargs):
        # Toggle: if the (user, message, emoji) row exists, delete it; otherwise create it.
        # Broadcasts a flat ``message.reaction_updated`` WS frame on commit.
        message = self.get_object()
        emoji = request.data.get("emoji_string")
        if not isinstance(emoji, str):
            return Response(
                {"emoji_string": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        emoji = emoji.strip()
        allowed = getattr(settings, "CHAT_REACTION_EMOJIS", ())
        if emoji not in allowed:
            return Response(
                {"emoji_string": ["Unsupported emoji."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            existing = (
                MessageReaction.objects
                .select_for_update()
                .filter(message=message, user=request.user, emoji=emoji)
                .first()
            )
            if existing is not None:
                existing.delete()
            else:
                MessageReaction.objects.create(
                    message=message, user=request.user, emoji=emoji
                )

        message = self._message_queryset().get(pk=message.pk)
        reactions = aggregate_reactions(message)
        _broadcast_reaction(message.group_id, message.id, reactions)
        return Response({"reactions": reactions}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="delivered")
    def delivered(self, request, *args, **kwargs):
        # Cursor semantics: mark this message AND all earlier messages in
        # the group as delivered for the caller. Idempotent. Never
        # downgrades a row that is already read. Mirrors the FE "device
        # received" double-tick — the WS consumer also fires this on
        # connect so explicit client calls are mostly a fallback.
        target = self.get_object()
        count = mark_delivered_cursor(request.user, target.group_id, target.id)
        return Response(
            {"marked_count": count, "up_to_id": target.id},
            status=status.HTTP_200_OK,
        )

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
