# Phase 2 update: updated views to use new message lifecycle fields.
# Changes: deleted_flag=False → deleted_at__isnull=True in queryset filters,
# destroy() now calls soft_delete() instead of setting deleted_flag,
# added partial_update() for editing messages which sets edited_at automatically,
# updated WebSocket broadcast payloads to use new field names.

from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Messages, MessageReaction
from .serializers import MessageSerializer, MessageUpdateSerializer, MessageReactionSerializer
from .management.permissions import IsGroupMemberOrAdmin, CanModerateMessage


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsGroupMemberOrAdmin]

    def get_permissions(self):
        if self.action == "destroy":
            return [CanModerateMessage()]
        return [IsGroupMemberOrAdmin()]

    def get_serializer_class(self):
        if self.action == "partial_update":
            return MessageUpdateSerializer
        return MessageSerializer

    def get_queryset(self):
        gid = self.kwargs.get("group_pk")
        # Phase 2 change: was deleted_flag=False, now uses deleted_at__isnull=True
        return (
            Messages.objects.filter(group_id=gid, deleted_at__isnull=True)
            .select_related("sender_user")
            .prefetch_related("resources__resource", "attachments")
        )

    # GET /chat/groups/{gid}/messages/
    # Uses cursor-based pagination (?after=<message_id>&limit=N) instead of the
    # project-default PageNumberPagination. Offset/page pagination is unsuitable
    # for real-time chat because new messages shift page boundaries between
    # requests, causing duplicates or gaps. Cursor pagination anchors on a
    # stable message ID so polling clients never miss or repeat a message.
    def list(self, request, *args, **kwargs):
        gid = self.kwargs.get("group_pk")
        # Phase 2 change: ordering uses sent_at instead of sent_datetime
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
        data = self.get_serializer(items, many=True).data
        next_after = items[0].id if items else None

        return Response(
            {"items": data, "next_after": next_after},
            status=status.HTTP_200_OK
        )

    # POST /chat/groups/{gid}/messages/
    def perform_create(self, serializer):
        gid = int(self.kwargs.get("group_pk"))
        msg = serializer.save(sender_user=self.request.user, group_id=gid)

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"group_{gid}",
            {
                "type": "chat.message",
                "payload": {
                    "event": "message.created",
                    "group_id": gid,
                    "message": {
                        "id": msg.id,
                        "sender_id": msg.sender_user_id,
                        "text": msg.message_text,
                        "message_type": msg.message_type,
                        # Phase 2 change: was sent_datetime, now sent_at
                        "sent_at": msg.sent_at.isoformat(),
                        "resource_ids": list(
                            msg.resources.values_list("resource_id", flat=True)
                        ),
                    },
                },
            },
        )

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        resp.status_code = status.HTTP_201_CREATED
        return resp

    # Phase 2 addition: PATCH /chat/groups/{gid}/messages/{id}/
    # Allows editing a message — automatically sets edited_at via MessageUpdateSerializer
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Broadcast edit event to WebSocket group
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"group_{instance.group_id}",
            {
                "type": "chat.message",
                "payload": {
                    "event": "message.edited",
                    "group_id": instance.group_id,
                    "message_id": instance.id,
                    "message_text": instance.message_text,
                    "edited_at": instance.edited_at.isoformat() if instance.edited_at else None,
                },
            },
        )
        return Response(MessageSerializer(instance).data)

    # DELETE /chat/groups/{gid}/messages/{id}/
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Phase 2 change: was instance.deleted_flag = True → instance.save()
        # Now calls soft_delete() which sets deleted_at = timezone.now()
        instance.soft_delete()

        # Broadcast delete event to WebSocket group
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"group_{instance.group_id}",
            {
                "type": "chat.message",
                "payload": {
                    "event": "message.deleted",
                    "group_id": instance.group_id,
                    "message_id": instance.id,
                },
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # POST /chat/groups/{gid}/messages/{id}/react/
    @action(detail=True, methods=["post"], url_path="react")
    def react(self, request, *args, **kwargs):
        instance = self.get_object()
        emoji = request.data.get("emoji_string", "").strip()

        if not emoji:
            return Response(
                {"detail": "emoji_string is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Toggle logic — add if not exists, remove if exists
        reaction, created = MessageReaction.objects.get_or_create(
            message=instance,
            user=request.user,
            emoji_string=emoji,
        )
        if not created:
            reaction.delete()

        # Build updated reaction counts by iterating all reactions for this message.
        # TODO: Replace with a single aggregated query using
        #       .values('emoji_string').annotate(count=Count('id')) to avoid
        #       loading every row into Python when a message has many reactions.
        all_reactions = MessageReaction.objects.filter(message=instance)
        reaction_counts = {}
        for r in all_reactions:
            reaction_counts[r.emoji_string] = reaction_counts.get(r.emoji_string, 0) + 1

        # Broadcast to WebSocket group
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"group_{instance.group_id}",
            {
                "type": "chat.message",
                "payload": {
                    "event": "message.reaction_updated",
                    "group_id": instance.group_id,
                    "message_id": instance.id,
                    "reactions": reaction_counts,
                },
            },
        )

        serializer = MessageReactionSerializer(
            {"message_id": instance.id, "reactions": reaction_counts}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)