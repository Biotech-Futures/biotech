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
from .models import (
    MessageAttachment,
    MessageMention,
    MessageReaction,
    MessageStatus,
    Messages,
)
from .serializers import (
    MentionSerializer,
    MessageAttachmentUploadSerializer,
    MessagePublicSerializer,
    MessageSerializer,
    MessageUpdateSerializer,
    aggregate_reactions,
)
from .services.storage import CHAT_FILE_SERVICE, stored_chat_file
from .utils import parse_mentions
from apps.groups.models import Groups, GroupMembership


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


def _broadcast_mention(user_id: int, payload: dict) -> None:
    """Push a ``mention.created`` event to a single user across all the
    devices/tabs they currently have connected.

    Per-user channel group ``user_{id}`` is joined by ``GroupChatConsumer``
    on connect (regardless of which group's WS the user happens to be on)
    so a mention in group A reaches the user even if their open socket is
    for group B's chat.
    """
    channel_layer = get_channel_layer()
    envelope = {
        "type": "chat.message",
        "payload": {
            "event": "mention.created",
            "type": "mention.created",
            **payload,
        },
    }

    def _send():
        async_to_sync(channel_layer.group_send)(f"user_{user_id}", envelope)

    transaction.on_commit(_send)


def apply_mentions(message) -> list[int]:
    """Parse ``<@N>`` tokens in ``message.message_text``, filter to
    active members of the message's group (excluding the sender), insert
    any new ``MessageMention`` rows, and broadcast ``mention.created`` to
    each newly mentioned user.

    Idempotent: re-running on an edited message that re-mentions the
    same user does *not* duplicate rows (unique_together) and does not
    re-broadcast. Mentions removed by an edit are intentionally left
    in place — the user was already notified once and the inbox entry
    should survive the sender's edits.

    Returns the list of user IDs that received a new mention row (for
    test introspection).
    """
    candidate_ids = parse_mentions(message.message_text or "")
    if not candidate_ids:
        return []
    # Drop self-mentions and any IDs outside the current active group
    # membership. The DB filter is the source of truth — never trust a
    # client-supplied ID list.
    candidate_ids.discard(message.sender_user_id)
    valid_ids = set(
        GroupMembership.objects
        .filter(
            group_id=message.group_id,
            user_id__in=candidate_ids,
            left_at__isnull=True,
        )
        .values_list("user_id", flat=True)
    )
    if not valid_ids:
        return []

    existing_ids = set(
        MessageMention.objects
        .filter(message=message, mentioned_user_id__in=valid_ids)
        .values_list("mentioned_user_id", flat=True)
    )
    to_create = valid_ids - existing_ids
    if not to_create:
        return []

    MessageMention.objects.bulk_create(
        [
            MessageMention(message=message, mentioned_user_id=uid)
            for uid in to_create
        ],
        ignore_conflicts=True,
    )

    payload = {
        "group_id": message.group_id,
        "message_id": message.id,
        "sender_user_id": message.sender_user_id,
        "preview": (message.message_text or "")[:140],
    }
    for uid in to_create:
        _broadcast_mention(uid, payload)
    return sorted(to_create)


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

    # GET /chat/groups/{gid}/messages/search/?q=&before=&limit=
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request, *args, **kwargs):
        gid = self.kwargs.get("group_pk")
        q = (request.query_params.get("q") or "").strip()
        if not q:
            return Response({"items": [], "next_before": None}, status=status.HTTP_200_OK)

        qs = (
            self.get_queryset()
            .filter(message_text__icontains=q)
            .order_by("-sent_at", "-id")
        )

        before = request.query_params.get("before")
        if before:
            try:
                pivot = Messages.objects.get(pk=int(before), group_id=gid)
                qs = qs.filter(
                    Q(sent_at__lt=pivot.sent_at)
                    | Q(sent_at=pivot.sent_at, id__lt=pivot.id)
                )
            except (ValueError, Messages.DoesNotExist):
                pass

        try:
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 50))

        items = list(qs[:limit])
        data = MessagePublicSerializer(items, many=True, context=self.get_serializer_context()).data
        # next_before is the oldest returned id when the page is full — null
        # signals end-of-results so the FE can stop paging.
        next_before = items[-1].id if len(items) == limit else None
        return Response(
            {"items": data, "next_before": next_before},
            status=status.HTTP_200_OK,
        )

    # POST /chat/groups/{gid}/messages/
    def perform_create(self, serializer):
        gid = int(self.kwargs.get("group_pk"))
        msg = serializer.save(sender_user=self.request.user, group_id=gid)
        apply_mentions(msg)
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
                apply_mentions(message)
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

        # Edits can introduce *new* mentions (existing ones are preserved
        # — see ``apply_mentions``'s contract).
        apply_mentions(instance)
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


class MentionViewSet(viewsets.GenericViewSet):
    """Per-user @mentions inbox.

    Scoped to ``request.user`` — the queryset never returns mentions for
    anyone else, so there is no group-level RBAC to enforce here; access
    is already restricted by ownership of the mention row.
    """

    serializer_class = MentionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            MessageMention.objects
            .filter(mentioned_user=self.request.user)
            .select_related("message", "message__sender_user")
            .order_by("-message__sent_at", "-id")
        )

    # GET /chat/mentions/?unread=true&limit=&before=
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        if request.query_params.get("unread", "").lower() == "true":
            qs = qs.filter(read_at__isnull=True)

        before = request.query_params.get("before")
        if before:
            try:
                pivot = (
                    MessageMention.objects
                    .filter(pk=int(before), mentioned_user=request.user)
                    .select_related("message")
                    .first()
                )
            except ValueError:
                pivot = None
            if pivot is not None:
                qs = qs.filter(
                    Q(message__sent_at__lt=pivot.message.sent_at)
                    | Q(message__sent_at=pivot.message.sent_at, id__lt=pivot.id)
                )

        try:
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 50))

        items = list(qs[:limit])
        unread_count = (
            MessageMention.objects
            .filter(mentioned_user=request.user, read_at__isnull=True)
            .count()
        )
        data = MentionSerializer(items, many=True).data
        next_before = items[-1].id if len(items) == limit else None
        return Response(
            {"items": data, "next_before": next_before, "unread_count": unread_count},
            status=status.HTTP_200_OK,
        )

    # POST /chat/mentions/{id}/read/
    @action(detail=True, methods=["post"], url_path="read")
    def read(self, request, *args, **kwargs):
        mention = self.get_queryset().filter(pk=kwargs.get("pk")).first()
        if mention is None:
            return Response(
                {"detail": "Mention not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if mention.read_at is None:
            mention.read_at = timezone.now()
            mention.save(update_fields=["read_at"])
        return Response(MentionSerializer(mention).data, status=status.HTTP_200_OK)
