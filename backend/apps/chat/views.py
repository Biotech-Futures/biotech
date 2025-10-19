import json, uuid, mimetypes
from django.db.models import Q
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Messages, MessageAttachments, MessageResource
from .serializers import MessageSerializer
from .management.permissions import IsGroupMemberOrAdmin,  CanModerateMessage
from .management.azure_storage import upload_stream, generate_sas_url

class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsGroupMemberOrAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # choose permissions per action
    def get_permissions(self):
        if self.action == "destroy":
            return [CanModerateMessage()]
        return [IsGroupMemberOrAdmin()]

    def get_queryset(self):
        gid = self.kwargs.get("group_pk")
        return (
            Messages.objects.filter(group_id=gid, deleted_flag=False)
            .select_related("sender_user")
            .prefetch_related("resources__resource", "attachments")
        )
    
    # --- #104: POST /groups/{id}/messages ---
    # --- #172: Message attachments ---
    def create(self, request, *args, **kwargs):
        gid = int(self.kwargs.get("group_pk"))
        user = request.user

        # Parse standard fields from multipart/form-data
        message_text = (request.data.get("message_text") or "").strip()

        # resources can be a JSON string: "[]" or "[1,2,3]"
        resources_raw = request.data.get("resources")
        resources_ids = []
        if resources_raw:
            try:
                resources_ids = json.loads(resources_raw)
                if not isinstance(resources_ids, list):
                    raise ValueError
            except Exception:
                return Response({"detail": "Invalid resources JSON (must be a list of IDs)."}, status=400)
            
        # files under attachments[]
        files = request.FILES.getlist("attachments")
        if len(files) > 10:
            return Response({"detail": "Maximum of 10 attachments per message."}, status=400)

        # Guardrails
        max_mb = getattr(settings, "CHAT_MAX_UPLOAD_MB", 25)
        allowed = getattr(settings, "CHAT_ALLOWED_MIME", {"image/png","image/jpeg","application/pdf"})
        max_bytes = max_mb * 1024 * 1024

        # Create the message first
        msg = Messages.objects.create(
            sender_user=user,
            group_id=gid,
            message_text=message_text,
        )

        # Link resources (if any)
        if resources_ids:
            MessageResource.objects.bulk_create([
                MessageResource(message=msg, resource_id=int(rid)) for rid in resources_ids
            ])

        # Upload each file to Azure, collect attachment rows
        to_create = []
        for f in files:
            if f.size > max_bytes:
                msg.delete()  # rollback
                return Response({"detail": f"File too large: {f.name}"}, status=413)

            mime = f.content_type or mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            if allowed and mime not in allowed:
                msg.delete()
                return Response({"detail": f"Unsupported file type: {f.name}"}, status=415)

            filename = f.name
            blob_name = f"group-chat/{gid}/{uuid.uuid4().hex}_{filename}"
            canonical_url = upload_stream(f, blob_name, content_type=mime)  # uploads; returns canonical (no SAS) URL

            to_create.append(MessageAttachments(
                message=msg,
                attachment_filename=filename,
                attachment_url=canonical_url,
            ))

        if to_create:
            MessageAttachments.objects.bulk_create(to_create)

        # Serialize response (serializer turns canonical URLs into SAS download links)
        data = MessageSerializer(msg).data

        # WS broadcast with short-lived SAS links
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
                        "sent_datetime": msg.sent_datetime.isoformat(),
                        "resource_ids": list(msg.resources.values_list("resource_id", flat=True)),
                        "attachments": [
                            {
                                "id": a.id,
                                "filename": a.attachment_filename,
                                "url": generate_sas_url(a.attachment_url),
                            } for a in msg.attachments.all()
                        ],
                    },
                },
            },
        )

        return Response(data, status=status.HTTP_201_CREATED)
    
    # --- #105: GET /groups/{id}/messages/?after={cursor}&limit={n} ---
    def list(self, request, *args, **kwargs):
        gid = self.kwargs.get("group_pk")
        qs = self.get_queryset().order_by("-sent_datetime", "-id")

        # cursor: items newer than this message id
        after = request.query_params.get("after")
        if after:
            try:
                pivot = Messages.objects.get(pk=int(after), group_id=gid)
                qs = qs.filter(
                    Q(sent_datetime__gt=pivot.sent_datetime) |
                    Q(sent_datetime=pivot.sent_datetime, id__gt=pivot.id)
                )
            except (ValueError, Messages.DoesNotExist):
                pass  # ignore bad cursor and return latest

        # limit (default 50, max 100, min 1)
        try:
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            limit = 50
        limit = 100 if limit > 100 else (1 if limit < 1 else limit)

        items = list(qs[:limit])
        data = self.get_serializer(items, many=True).data
        next_after = items[0].id if items else None

        return Response({"items": data, "next_after": next_after}, status=status.HTTP_200_OK)
    
    # --- #106: DELETE /groups/{gid}/messages/{mid} (soft-delete + WS) ---
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()  # permission already checked on object
        instance.deleted_flag = True
        instance.save(update_fields=["deleted_flag"])

        # broadcast deletion to group room
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


