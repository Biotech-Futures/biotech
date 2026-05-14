from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from rest_framework import serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.storage import serve_managed_file
from apps.audit.services import log_audit_event
from .management.permissions import (
    CanEditMessage,
    CanModerateMessage,
    IsGroupMemberOrAdmin,
)
from .rbac import can_access_chat_group
from .models import (
    MessageAttachment,
    MessageGif,
    MessageMention,
    MessagePreview,
    MessageReaction,
    MessageStatus,
    Messages,
    MessageType,
)
from .og_extractor import extract_urls
from .serializers import (
    MentionSerializer,
    MessageAttachmentUploadSerializer,
    MessageGifCreateSerializer,
    MessagePublicSerializer,
    MessageSerializer,
    MessageUpdateSerializer,
    aggregate_reactions,
)
from .services.gifs import cached_fetch, clamp_limit, clamp_pos, clamp_query
from .services.storage import CHAT_FILE_SERVICE, stored_chat_file
from .tasks import dispatch_og
from .utils import contains_blacklisted, parse_mentions
from apps.groups.models import Groups, GroupMembership
from apps.users.utils.admin_scope import can_admin_track, is_operational_admin


def _broadcast(group_id: int, event: str, message_payload: dict) -> None:
    """Fan a message-scoped chat event out to every consumer subscribed
    to ``group_id``.

    Wrapped in ``transaction.on_commit`` so a rolled-back DB write never
    produces a phantom WebSocket event. Envelope shape is the single
    contract documented at the top of
    ``apps/chat/management/consumers.py``.

    The wire payload always carries: ``event``, ``type`` (mirror of
    event), ``group_id``, ``message_id``, and ``message`` (full
    serializer output). The duplicated ``type``/``event`` matches the
    other (non-message) broadcasts so clients can branch on a single
    key consistently.
    """
    channel_layer = get_channel_layer()
    envelope = {
        "type": "chat.message",
        "payload": {
            "event": event,
            "type": event,
            "group_id": group_id,
            "message_id": message_payload.get("id"),
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
        if self.action == "restore":
            # Restore is admin recovery, not sender self-undo; object track scope
            # is checked inside restore() after the deleted row is loaded.
            return [IsAuthenticated()]
        if self.action == "partial_update":
            # Edit and delete share the same window-bounded RBAC rule, but the
            # permission classes stay split so view wiring expresses intent.
            return [IsAuthenticated(), CanEditMessage()]
        if self.action in {"upload", "attachment_download", "send_gif"}:
            return [IsAuthenticated()]
        if self.action in {"read", "delivered", "react", "message_status"}:
            return [IsAuthenticated(), IsGroupMemberOrAdmin()]
        return [IsGroupMemberOrAdmin()]

    def get_serializer_class(self):
        if self.action == "upload":
            return MessageAttachmentUploadSerializer
        if self.action == "send_gif":
            return MessageGifCreateSerializer
        if self.action == "partial_update":
            return MessageUpdateSerializer
        if self.action == "retrieve":
            return MessagePublicSerializer
        return MessageSerializer

    def _message_queryset(self, *, include_deleted=False):
        # ``reply_to`` is select_related so the embedded parent context
        # does not issue an extra query per row. The join is intentionally
        # one level deep — mirroring ReplyToSerializer's bounded shape —
        # so a long chain of quotes still costs exactly one extra JOIN.
        user_id = getattr(getattr(self, "request", None), "user", None)
        user_id = getattr(user_id, "id", None)
        # Restore/deleted admin paths opt into tombstoned rows; normal chat stays active-only.
        base_qs = Messages.objects.all() if include_deleted else Messages.objects.filter(deleted_at__isnull=True)
        return (
            base_qs
            .select_related("sender_user", "reply_to", "preview", "gif")
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
        return self._message_queryset(
            include_deleted=self.action in {"restore"}
        ).filter(group_id=gid)

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
                    Messages.objects.select_related("sender_user", "reply_to", "preview", "gif")
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
        public = MessagePublicSerializer(message, context=context).data
        # MessageSerializer's nested attachments lack download_url; rebuild from
        # the public shape that does include it.
        data["attachments"] = public.get("attachments", [])
        # ``preview`` only lives on MessagePublicSerializer — surface it on
        # the broadcast so a client receiving the WS frame after a preview
        # has been resolved (or cleared by edit) doesn't need to round-trip
        # the REST list endpoint.
        data["preview"] = public.get("preview")
        # ``gif`` is rendered through SerializerMethodField on both serializers,
        # but the public one is the canonical wire shape — keep parity so the
        # broadcast and REST payloads match for GIF messages too.
        data["gif"] = public.get("gif")
        return data

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

    def _get_group(self):
        group_pk = self.kwargs.get("group_pk")
        return Groups.objects.only("id", "track_id").filter(
            pk=group_pk,
            deleted_at__isnull=True,
        ).first()

    # GET /chat/groups/{gid}/messages/?after=&before=&limit=
    def list(self, request, *args, **kwargs):
        # Two cursors so the same endpoint serves both real chat-UX
        # operations: ``after`` returns messages strictly newer than the
        # pivot (poll-on-reconnect), ``before`` returns messages strictly
        # older (scroll-up infinite history). Both may be combined to
        # bound a window.
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
        limit = max(1, min(limit, 100))

        items = list(qs[:limit])
        data = MessagePublicSerializer(items, many=True, context=self.get_serializer_context()).data
        # ``next_after`` = newest id on the page; pass back as ``after``
        # to poll for what arrived since. ``next_before`` = oldest id on
        # a *full* page; pass back as ``before`` to load older history.
        # Null cursor in either direction signals "no more in that direction".
        next_after = items[0].id if items else None
        next_before = items[-1].id if len(items) == limit else None

        return Response(
            {"items": data, "next_after": next_after, "next_before": next_before},
            status=status.HTTP_200_OK,
        )

    # GET /chat/groups/{gid}/messages/search/?q=&before=&limit=&type=&from=&to=
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request, *args, **kwargs):
        gid = self.kwargs.get("group_pk")
        q = (request.query_params.get("q") or "").strip()
        # Filters are optional refinements; a search with only filters and
        # no ``q`` is still useful ("all GIFs from last week") so we don't
        # short-circuit on an empty q anymore — the filters can stand alone.
        filter_type = (request.query_params.get("type") or "").strip().lower()
        filter_from = (request.query_params.get("from") or "").strip()
        filter_to = (request.query_params.get("to") or "").strip()

        if not q and not filter_type and not filter_from and not filter_to:
            return Response({"items": [], "next_before": None}, status=status.HTTP_200_OK)

        qs = self.get_queryset().order_by("-sent_at", "-id")
        if q:
            qs = qs.filter(message_text__icontains=q)

        # ``text`` / ``gif`` map directly to ``message_type``. ``attachment``
        # and ``resource`` are stored as ``message_type='attachment'`` /
        # ``'resource'`` already, so the same column filter covers them.
        if filter_type in {"text", "attachment", "resource", "gif"}:
            qs = qs.filter(message_type=filter_type)

        # Date filters are inclusive whole-day windows in the server's TZ.
        # Bad input is silently ignored rather than 400-ing — the FE
        # surfaces a date-picker so the value is always YYYY-MM-DD in
        # the happy path; defensive parsing keeps a typo from breaking
        # the search panel.
        if filter_from:
            try:
                qs = qs.filter(sent_at__date__gte=filter_from)
            except (ValueError, TypeError):
                pass
        if filter_to:
            try:
                qs = qs.filter(sent_at__date__lte=filter_to)
            except (ValueError, TypeError):
                pass

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

    @action(detail=False, methods=["get"], url_path="deleted")
    def deleted(self, request, *args, **kwargs):
        # Recovery queue for moderators; participants should never browse deleted content.
        if not is_operational_admin(request.user):
            return Response({"detail": "Admin access is required."}, status=status.HTTP_403_FORBIDDEN)

        gid = self.kwargs.get("group_pk")
        qs = (
            self._message_queryset(include_deleted=True)
            .filter(group_id=gid, deleted_at__isnull=False)
            .order_by("-deleted_at", "-id")
        )
        try:
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 100))
        items = list(qs[:limit])
        return Response(
            {"items": MessageSerializer(items, many=True, context=self.get_serializer_context()).data},
            status=status.HTTP_200_OK,
        )

    # POST /chat/groups/{gid}/messages/
    def perform_create(self, serializer):
        gid = int(self.kwargs.get("group_pk"))
        msg = serializer.save(sender_user=self.request.user, group_id=gid)
        apply_mentions(msg)
        _broadcast(gid, "message.created", self._serialize_broadcast_message(msg))
        self._dispatch_link_previews(msg)

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
                # Attachment captions can carry URLs too — keep unfurl behavior
                # uniform with the plain-text POST path. Dispatch is on_commit,
                # so a failed transaction still cleans up cleanly.
                self._dispatch_link_previews(message)
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
        # Keep the persisted OG preview in sync with the edited text.
        # update_or_create on the worker side handles URL *changes*, so
        # the only case the dispatcher doesn't cover is "edit removed
        # the last URL" — drop the stale row here so the broadcast
        # below carries ``preview:null`` and the FE doesn't render a
        # zombie card.
        if extract_urls(instance.message_text):
            self._dispatch_link_previews(instance)
        else:
            MessagePreview.objects.filter(message_id=instance.id).delete()
            # Invalidate the select_related cache so the immediately-
            # following serialization sees ``preview = None``.
            if hasattr(instance, "_state"):
                instance._state.fields_cache.pop("preview", None)

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

    @action(detail=True, methods=["post"], url_path="restore")
    @transaction.atomic
    def restore(self, request, *args, **kwargs):
        instance = self.get_object()
        if not is_operational_admin(request.user) or not can_admin_track(
            request.user, instance.group.track_id
        ):
            return Response(
                {"detail": "Admin access is required to restore messages."},
                status=status.HTTP_403_FORBIDDEN,
            )
        # A message can only return while its parent group is active.
        if instance.group.deleted_at is not None:
            raise drf_serializers.ValidationError(
                {"group": ["Cannot restore a message in a deleted group."]}
            )
        if instance.deleted_at is None:
            return Response(
                MessageSerializer(instance, context=self.get_serializer_context()).data,
                status=status.HTTP_200_OK,
            )

        before_state = MessageSerializer(instance, context=self.get_serializer_context()).data
        instance.restore()
        instance.refresh_from_db()
        after_state = MessageSerializer(instance, context=self.get_serializer_context()).data
        log_audit_event(
            actor=request.user,
            entity_type="message",
            entity_id=instance.id,
            action="restore",
            before_state=before_state,
            after_state=after_state,
        )
        _broadcast(
            instance.group_id,
            "message.restored",
            self._serialize_broadcast_message(instance),
        )
        return Response(after_state, status=status.HTTP_200_OK)

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
        # One reaction per (user, message): reacting with the same emoji toggles
        # it off; reacting with a different emoji REPLACES the previous one so a
        # user can never carry multiple chips on the same message. Same WS
        # ``message.reaction_updated`` frame is broadcast on commit either way.
        message = self.get_object()
        emoji = request.data.get("emoji")
        if not isinstance(emoji, str):
            raise drf_serializers.ValidationError({"emoji": ["This field is required."]})
        emoji = emoji.strip()
        allowed = getattr(settings, "CHAT_REACTION_EMOJIS", ())
        if emoji not in allowed:
            raise drf_serializers.ValidationError({"emoji": ["Unsupported emoji."]})

        with transaction.atomic():
            existing_for_user = list(
                MessageReaction.objects
                .select_for_update()
                .filter(message=message, user=request.user)
            )
            same = next((r for r in existing_for_user if r.emoji == emoji), None)
            if same is not None:
                # Toggle off — user re-tapped the emoji they already chose.
                same.delete()
            else:
                # Replace: drop any prior emoji from this user on this message
                # before recording the new one. ``existing_for_user`` is already
                # narrow (1 row in normal use) so this stays cheap.
                if existing_for_user:
                    MessageReaction.objects.filter(
                        pk__in=[r.pk for r in existing_for_user]
                    ).delete()
                MessageReaction.objects.create(
                    message=message, user=request.user, emoji=emoji,
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

    @action(detail=False, methods=["post"], url_path="send-gif")
    def send_gif(self, request, *args, **kwargs):
        """Create a ``message_type=GIF`` message + sidecar in one transaction.

        The Tenor URL is stored verbatim — we trust the provider URL we
        already proxied. Captions still flow through ``sanitize_text`` via
        :class:`MessageGifCreateSerializer.validate_message_text`, so a GIF
        send can't bypass the chat moderation filter.

        Broadcast and unfurl semantics mirror ``perform_create`` so the FE
        renders a GIF bubble the same way it renders a text one.
        """
        group = self._get_group()
        if group is None:
            return Response({"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_access_chat_group(request.user, group):
            return Response(
                {"detail": "You do not have access to this group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = MessageGifCreateSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        gid = group.id

        with transaction.atomic():
            message = Messages.objects.create(
                sender_user=request.user,
                group_id=gid,
                message_type=MessageType.GIF,
                message_text=data.get("message_text", ""),
                reply_to=data.get("reply_to"),
            )
            MessageGif.objects.create(
                message=message,
                provider=data.get("provider", "tenor"),
                provider_id=data["provider_id"],
                gif_url=data["gif_url"],
                preview_url=data.get("preview_url", ""),
                title=data.get("title", ""),
            )
            apply_mentions(message)
            _broadcast(gid, "message.created", self._serialize_broadcast_message(message))
            # Captions can still carry URLs — keep unfurl symmetric with
            # plain text + attachment sends.
            self._dispatch_link_previews(message)

        return Response(
            self._serialize_public_message(message), status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="status")
    def message_status(self, request, *args, **kwargs):
        """Return the per-user delivery + read state for one message.

        Powers the FE's "Read by N" popover. Excludes the sender from both
        lists (the sender has no ``MessageStatus`` row of their own). Names
        come from ``Users.get_full_name()`` so the FE renders the same
        attribution string used elsewhere in chat.
        """
        message = self.get_object()
        statuses = (
            MessageStatus.objects
            .filter(message_id=message.id)
            .exclude(user_id=message.sender_user_id)
            .select_related("user")
            .order_by("-read_at", "-delivered_at", "id")
        )

        read_by = []
        delivered_by = []
        for s in statuses:
            user = s.user
            name = user.get_full_name() if user else f"User {s.user_id}"
            if s.read_at is not None:
                read_by.append({"id": s.user_id, "name": name, "read_at": s.read_at})
            elif s.delivered_at is not None:
                delivered_by.append(
                    {"id": s.user_id, "name": name, "delivered_at": s.delivered_at}
                )

        return Response(
            {"read_by": read_by, "delivered_by": delivered_by},
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

        # ``?inline=1`` flips ``Content-Disposition`` from ``attachment`` to
        # ``inline`` so the browser previews the file in a tab (PDF viewer,
        # image, etc.) instead of forcing a save. Without the flag the default
        # download semantics stand — keeps existing callers that only want
        # the save flow unchanged.
        inline = (request.query_params.get("inline") or "").lower() in {"1", "true", "yes"}
        return serve_managed_file(
            resolve_url=CHAT_FILE_SERVICE.resolve_url,
            open_file=CHAT_FILE_SERVICE.open,
            storage_key=attachment.storage_key,
            filename=attachment.attachment_filename,
            mime_type=attachment.attachment_mime_type,
            size=attachment.attachment_size,
            as_attachment=not inline,
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

    # POST /chat/mentions/mark-all-read/
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request, *args, **kwargs):
        """Clear the entire mentions inbox in one call.

        Idempotent — an already-empty inbox returns ``marked_count: 0``.
        Scope is always ``request.user``; no user/group filter is
        accepted on the body so a compromised client can never escalate
        to clearing someone else's notifications.
        """
        updated = (
            MessageMention.objects
            .filter(mentioned_user=request.user, read_at__isnull=True)
            .update(read_at=timezone.now())
        )
        return Response(
            {"marked_count": updated, "unread_count": 0},
            status=status.HTTP_200_OK,
        )


class GifViewSet(viewsets.ViewSet):
    """Tenor GIF proxy + sanitised search.

    Endpoints:
      * GET /api/v1/chat/gifs/search?q=&pos=&limit=
      * GET /api/v1/chat/gifs/trending?pos=&limit=

    Per issue #95, any query containing a blacklisted stem/whole-word
    returns ``{items: [], next_pos: null}`` immediately without reaching
    Tenor. This is layered on top of Tenor's own ``contentfilter=high``
    so we still blank slurs even if upstream filtering ever loosens.
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request, *args, **kwargs):
        query = clamp_query(request.query_params.get("q"))
        pos = clamp_pos(request.query_params.get("pos"))
        limit = clamp_limit(request.query_params.get("limit"))

        if not query:
            return Response(
                {"items": [], "next_pos": None}, status=status.HTTP_200_OK,
            )

        # Issue #95 contract: ill / irrelevant words -> blank output. The
        # check runs BEFORE any provider call so we never spend the Tenor
        # rate-limit budget on a query we wouldn't surface anyway, and a
        # malicious client cannot use the chat as a slur-aware GIF lookup.
        if contains_blacklisted(query):
            return Response(
                {"items": [], "next_pos": None}, status=status.HTTP_200_OK,
            )

        payload = cached_fetch("search", query, pos, limit)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="trending")
    def trending(self, request, *args, **kwargs):
        pos = clamp_pos(request.query_params.get("pos"))
        limit = clamp_limit(request.query_params.get("limit"))
        payload = cached_fetch("featured", "", pos, limit)
        return Response(payload, status=status.HTTP_200_OK)
