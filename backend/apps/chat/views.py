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

from .contracts import build_chat_message_payload
from .models import Messages, MessageReaction
from .serializers import MessageSerializer, MessageUpdateSerializer, MessageReactionSerializer, ReactRequestSerializer
from .management.permissions import IsGroupMemberOrAdmin, CanModerateMessage
from .tasks import enqueue_process_chat_message_created


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
        # Scopes all queryset access (including get_object()) to this group,
        # so a user cannot react to a message in another group by guessing its ID.
        return (
            Messages.objects.filter(group_id=gid, deleted_at__isnull=True)
            .select_related("sender_user")
            .prefetch_related("resources__resource", "reactions", "statuses")
        )

    # GET /api/v1/chat/groups/{gid}/messages/
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
        data = [build_chat_message_payload(item) for item in items]
        next_after = items[0].id if items else None

        return Response(
            {"items": data, "next_after": next_after},
            status=status.HTTP_200_OK
        )

    def _broadcast_payload(self, group_id, payload):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"conversation_{group_id}",
            {
                "type": "chat.message",
                "payload": payload,
            },
        )

    # POST /api/v1/chat/groups/{gid}/messages/
    def perform_create(self, serializer):
        gid = int(self.kwargs.get("group_pk"))
        msg = serializer.save(sender_user=self.request.user, group_id=gid)
        payload = {
            "type": "message.created",
            "message": build_chat_message_payload(msg),
        }
        self._broadcast_payload(gid, payload)
        enqueue_process_chat_message_created(msg.id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        message = Messages.objects.select_related("sender_user").prefetch_related(
            "resources__resource", "reactions", "statuses"
        ).get(pk=serializer.instance.pk)
        headers = self.get_success_headers(serializer.data)
        return Response(build_chat_message_payload(message), status=status.HTTP_201_CREATED, headers=headers)

    # PATCH /api/v1/chat/groups/{gid}/messages/{id}/
    # Allows editing a message — automatically sets edited_at via MessageUpdateSerializer
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        instance = Messages.objects.select_related("sender_user").prefetch_related(
            "resources__resource", "reactions", "statuses"
        ).get(pk=instance.pk)
        self._broadcast_payload(
            instance.group_id,
            {
                "type": "message.edited",
                "conversation_id": instance.group_id,
                "message_id": instance.id,
                "edited_at": instance.edited_at.isoformat() if instance.edited_at else None,
                "message": build_chat_message_payload(instance),
            },
        )
        return Response(build_chat_message_payload(instance))

    # DELETE /api/v1/chat/groups/{gid}/messages/{id}/
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Phase 2 change: was instance.deleted_flag = True → instance.save()
        # Now calls soft_delete() which sets deleted_at = timezone.now()
        instance.soft_delete()

        self._broadcast_payload(
            instance.group_id,
            {
                "type": "message.deleted",
                "conversation_id": instance.group_id,
                "message_id": instance.id,
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # POST /api/v1/chat/groups/{gid}/messages/{id}/react/
    @action(detail=True, methods=["post"], url_path="react")
    def react(self, request, *args, **kwargs):
        # get_object() uses get_queryset() which is already scoped to group_pk
        instance = self.get_object()

        req_serializer = ReactRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        emoji = req_serializer.validated_data["emoji_string"]

        # Toggle logic — add if not exists, remove if exists
        reaction, created = MessageReaction.objects.get_or_create(
            message=instance,
            user=request.user,
            emoji_string=emoji,
        )
        if not created:
            reaction.delete()

        # Build updated reaction counts
        all_reactions = MessageReaction.objects.filter(message=instance)
        reaction_counts = {}
        for r in all_reactions:
            reaction_counts[r.emoji_string] = reaction_counts.get(r.emoji_string, 0) + 1

        self._broadcast_payload(
            instance.group_id,
            {
                "type": "message.reaction_updated",
                "conversation_id": instance.group_id,
                "message_id": instance.id,
                "reactions": reaction_counts,
            },
        )

        serializer = MessageReactionSerializer(
            {"message_id": instance.id, "reactions": reaction_counts}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
