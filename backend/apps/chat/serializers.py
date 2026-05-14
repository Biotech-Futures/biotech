from django.conf import settings
from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.common.filenames import sanitize_upload_filename
from apps.common.upload_validation import validate_uploaded_file
from apps.resources.models import Resources

from .models import (
    MessageAttachment,
    MessageGif,
    MessageMention,
    MessageReaction,
    MessageResource,
    MessageStatus,
    Messages,
    MessageType,
)
from .services.storage import stored_chat_file
from .utils import sanitize_text


def aggregate_reactions(message):
    """Group reactions on a message into the public payload shape.

    Returns ``{emoji: {"count": int, "users": [{"id", "name"}, ...]}}``.
    Iterates the prefetched ``message.reactions.all()`` to avoid an
    extra query per message in list endpoints.
    """
    bucket = {}
    for reaction in message.reactions.all():
        entry = bucket.setdefault(
            reaction.emoji, {"count": 0, "users": []}
        )
        entry["count"] += 1
        entry["users"].append(
            {
                "id": reaction.user_id,
                "name": reaction.user.get_full_name(),
            }
        )
    return bucket


class MessageResourceSerializer(serializers.ModelSerializer):
    resource_id = serializers.PrimaryKeyRelatedField(
        queryset=Resources.objects.all(),
        source="resource",
        write_only=True,
    )
    resource_name = serializers.CharField(
        source="resource.name", read_only=True
    )

    class Meta:
        model = MessageResource
        fields = ["id", "resource_id", "resource_name"]


class MessageResourcePublicSerializer(serializers.ModelSerializer):
    resource_id = serializers.IntegerField(read_only=True)
    resource_name = serializers.CharField(source="resource.name", read_only=True)

    class Meta:
        model = MessageResource
        fields = ["resource_id", "resource_name"]


class MessageStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageStatus
        fields = ["id", "user", "status", "delivered_at", "read_at"]
        read_only_fields = ["id", "delivered_at", "read_at"]


class MessageGifSerializer(serializers.ModelSerializer):
    """Read-side projection of the GIF sidecar attached to a ``MessageType.GIF`` message."""

    class Meta:
        model = MessageGif
        fields = ["provider", "provider_id", "gif_url", "preview_url", "title"]
        read_only_fields = fields


class MessageAttachmentSerializer(serializers.ModelSerializer):
    attachment_filename = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = MessageAttachment
        fields = [
            "id",
            "attachment_filename",
            "attachment_mime_type",
            "attachment_size",
            "download_url",
        ]
        read_only_fields = fields

    def get_attachment_filename(self, obj):
        return sanitize_upload_filename(obj.attachment_filename)

    def get_download_url(self, obj):
        request = self.context.get("request")
        group_pk = self.context.get("group_pk") or obj.message.group_id
        path = reverse(
            "group-messages-attachment-download",
            kwargs={
                "group_pk": group_pk,
                "pk": obj.message_id,
                "attachment_pk": obj.id,
            },
            request=request,
        )
        # List/detail serializers can build absolute URLs when DRF has a request, but
        # tests and non-request code paths still need a stable fallback.
        if request is not None or not getattr(settings, "BACKEND_URL", ""):
            return path
        return f"{settings.BACKEND_URL.rstrip('/')}{path}"


class ReplyToSerializer(serializers.ModelSerializer):
    """Lightweight, *non-recursive* projection of a parent message used to
    embed quoted-reply context inside a child message's payload.

    Field-naming choice
    -------------------
    Uses the short keys ``text`` and ``user_id`` instead of the parent
    ``MessageSerializer``'s ``message_text`` / ``sender_user_id``. The
    nested object is rendered inside chat bubbles, where the FE benefits
    from a compact shape; the full schema is still available on the
    *child* message itself.

    Soft-deleted parents
    --------------------
    If the parent has been moderated away (``deleted_at`` is not null),
    the embedded payload still surfaces ``id`` and ``user_id`` (so the
    FE can render an attribution placeholder) but ``text`` is nulled
    and ``deleted: true`` is set. This prevents soft-deleted content
    from leaking through every child message that quoted it.

    Recursion bound
    ---------------
    The serializer does **not** itself include a ``reply_to`` field, so
    the response is flat at exactly one level of nesting regardless of
    how deep the underlying chain of quoted replies is. That is the
    structural recursion guard for the API (see
    ``test_reply_to_nesting_serialization``).
    """

    text = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source="sender_user_id", read_only=True)
    user_name = serializers.SerializerMethodField()
    deleted = serializers.SerializerMethodField()

    class Meta:
        model = Messages
        fields = ["id", "text", "user_id", "user_name", "deleted"]
        read_only_fields = fields

    def get_user_name(self, obj):
        # Reply previews need the author's display name so the FE can render
        # "Reply to Alice" rather than "Reply to User 36". For soft-deleted
        # parents we still surface the name — the placeholder rendering uses
        # ``deleted: true`` to suppress sensitive text but the author is
        # already public via mentions / message history.
        sender = getattr(obj, "sender_user", None)
        if sender is None:
            return ""
        return sender.get_full_name() or sender.get_username() or ""

    def get_text(self, obj):
        if obj.deleted_at is not None:
            return None
        return obj.message_text

    def get_deleted(self, obj):
        return obj.deleted_at is not None


class ReplyToIdField(serializers.PrimaryKeyRelatedField):
    """Write-side companion to :class:`ReplyToSerializer`.

    The queryset is restricted to the **current group's non-deleted
    messages**, consolidating two invariants in the canonical DRF place
    (the field's queryset) so they cannot drift:

    * Cross-group leak: a reply in group A cannot point at a parent in
      group B — such a PK is simply not in the queryset, so DRF rejects
      with the standard ``"Invalid pk \\"X\\" - object does not exist."``
      error. The generic message is also a small security win — it does
      not leak the existence of messages in other groups.
    * Soft-deleted parents: a reply cannot point at a moderated-away
      parent on creation.

    Fail-closed: if the serializer is ever instantiated outside a view
    (management command, signal handler, future bulk import) the
    queryset is empty, so any ``reply_to_id`` is rejected. Skipping the
    check on missing context — as some earlier drafts did — would be
    the opposite of what a security-relevant validator should do.
    """

    def get_queryset(self):
        view = self.context.get("view")
        if view is None:
            return Messages.objects.none()
        group_pk = view.kwargs.get("group_pk")
        if group_pk is None:
            return Messages.objects.none()
        return Messages.objects.filter(
            group_id=group_pk,
            deleted_at__isnull=True,
        )


class MessageSerializer(serializers.ModelSerializer):
    resources = MessageResourceSerializer(many=True, required=False)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    sender_name = serializers.CharField(
        source="sender_user.get_full_name", read_only=True
    )
    is_deleted = serializers.BooleanField(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    reactions = serializers.SerializerMethodField()
    read_count = serializers.IntegerField(source="_read_count", read_only=True, default=0)
    delivered_count = serializers.IntegerField(source="_delivered_count", read_only=True, default=0)
    is_read_by_me = serializers.BooleanField(source="_is_read_by_me", read_only=True, default=False)
    is_delivered_to_me = serializers.BooleanField(source="_is_delivered_to_me", read_only=True, default=False)

    # Read: nested lightweight parent context (or null if not a reply).
    # Write: ``reply_to_id`` accepts a PK constrained to the current
    # group's non-deleted messages — see ``ReplyToIdField``.
    reply_to = ReplyToSerializer(read_only=True)
    reply_to_id = ReplyToIdField(
        source="reply_to",
        write_only=True,
        required=False,
        allow_null=True,
    )
    gif = serializers.SerializerMethodField()

    class Meta:
        model = Messages
        fields = [
            "id",
            "group",
            "sender_user",
            "sender_name",
            "message_text",
            "message_type",
            "sent_at",
            "edited_at",
            "deleted_at",
            "is_deleted",
            "is_edited",
            "attachments",
            "resources",
            "reactions",
            "read_count",
            "delivered_count",
            "is_read_by_me",
            "is_delivered_to_me",
            "reply_to",
            "reply_to_id",
            "gif",
        ]
        read_only_fields = [
            "id", "group", "sender_user",
            "sent_at", "edited_at", "deleted_at",
        ]

    def get_reactions(self, obj):
        return aggregate_reactions(obj)

    def get_gif(self, obj):
        # Reverse OneToOne raises DoesNotExist when no row — guard with
        # ``getattr`` so messages without a GIF sidecar serialize as
        # ``gif: null`` instead of raising.
        gif = getattr(obj, "gif", None)
        if gif is None:
            return None
        return MessageGifSerializer(gif).data

    def create(self, validated_data):
        resources_data = validated_data.pop("resources", [])
        message = Messages.objects.create(**validated_data)
        for r in resources_data:
            MessageResource.objects.create(
                message=message, resource=r["resource"]
            )
        return message

    def validate(self, attrs):
        msg = attrs.get("message_text", "").strip()
        resources_data = self.initial_data.get("resources", [])
        message_type = attrs.get("message_type") or getattr(self.instance, "message_type", None)
        # GIF messages are created via a dedicated ``send-gif`` action and
        # may legitimately have empty caption text. Other types still
        # require text or a resource — empty rows would render as blank
        # bubbles, which is worse than rejecting them on the write side.
        if message_type != MessageType.GIF and not msg and not resources_data:
            raise serializers.ValidationError(
                "Message must include text or at least one resource."
            )
        # Sanitise BEFORE serializer.save() so the moderated text is what
        # gets persisted. Doing this here keeps the rule decoupled from
        # the view and ensures every write path goes through the same filter.
        if "message_text" in attrs:
            attrs["message_text"] = sanitize_text(attrs["message_text"])
        return attrs


class MessagePublicSerializer(serializers.ModelSerializer):
    resources = MessageResourcePublicSerializer(many=True, read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    sender_name = serializers.CharField(
        source="sender_user.get_full_name", read_only=True
    )
    is_edited = serializers.BooleanField(read_only=True)
    reactions = serializers.SerializerMethodField()
    read_count = serializers.IntegerField(source="_read_count", read_only=True, default=0)
    delivered_count = serializers.IntegerField(source="_delivered_count", read_only=True, default=0)
    is_read_by_me = serializers.BooleanField(source="_is_read_by_me", read_only=True, default=False)
    is_delivered_to_me = serializers.BooleanField(source="_is_delivered_to_me", read_only=True, default=False)
    # Embedded parent context for quoted replies. Same flat shape as
    # MessageSerializer's ``reply_to`` — see ``ReplyToSerializer`` for
    # the recursion-bound rationale.
    reply_to = ReplyToSerializer(read_only=True)
    # Persisted OG preview — same wire shape as the ``message.preview_ready``
    # WS event so the FE renderer can be one code path. ``None`` when the
    # message has no URL or the worker hasn't completed yet.
    preview = serializers.SerializerMethodField()
    # Nested GIF sidecar for ``message_type == 'gif'`` rows.
    gif = serializers.SerializerMethodField()

    class Meta:
        model = Messages
        fields = [
            "id",
            "sender_name",
            "message_text",
            "message_type",
            "sent_at",
            "edited_at",
            "is_edited",
            "attachments",
            "resources",
            "reactions",
            "read_count",
            "delivered_count",
            "is_read_by_me",
            "is_delivered_to_me",
            "reply_to",
            "preview",
            "gif",
        ]
        read_only_fields = fields

    def get_reactions(self, obj):
        return aggregate_reactions(obj)

    def get_preview(self, obj):
        # Reverse OneToOne raises DoesNotExist when no row — guard so
        # missing previews surface as ``None`` instead of an exception.
        preview = getattr(obj, "preview", None)
        if preview is None:
            return None
        return preview.to_payload()

    def get_gif(self, obj):
        gif = getattr(obj, "gif", None)
        if gif is None:
            return None
        return MessageGifSerializer(gif).data


class MessageAttachmentUploadSerializer(serializers.Serializer):
    message_text = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    uploaded_file = serializers.FileField(required=True)
    # Optional reply target so the multipart upload path supports the same
    # quoted-reply UX as the JSON message-create path. Same queryset / cross-
    # group invariants as :class:`ReplyToIdField`.
    reply_to_id = ReplyToIdField(
        source="reply_to",
        required=False,
        allow_null=True,
    )

    def validate_message_text(self, value):
        return sanitize_text((value or "").strip())

    def validate_uploaded_file(self, value):
        return validate_uploaded_file(
            value,
            max_size=settings.CHAT_ATTACHMENT_MAX_UPLOAD_SIZE,
            allowed_extensions=settings.CHAT_ATTACHMENT_ALLOWED_EXTENSIONS,
            allowed_mime_types=settings.CHAT_ATTACHMENT_ALLOWED_MIME_TYPES,
            field_label="Chat attachment",
        )

    def create(self, validated_data):
        # The view supplies pre-stored attachment metadata via context so the blob
        # upload spans the surrounding transaction.atomic() block — that way an
        # error in the view's broadcast step (after this returns) still triggers
        # blob cleanup on rollback. See MessageViewSet.upload.
        attachment_data = self.context.get("attachment_data")
        if attachment_data is None:
            raise RuntimeError(
                "MessageAttachmentUploadSerializer.create requires 'attachment_data' "
                "in context (the view manages the storage lifecycle)."
            )
        validated_data.pop("uploaded_file", None)
        message = Messages.objects.create(
            **validated_data,
            message_type=MessageType.ATTACHMENT,
        )
        MessageAttachment.objects.create(message=message, **attachment_data)
        return message


class MentionSerializer(serializers.ModelSerializer):
    """Inbox row for ``GET /chat/mentions/``.

    Embeds enough of the source message and group context that the FE
    can render a list item without a second fetch, but stays
    intentionally flat — full message detail (attachments, reactions,
    full reply chain) is still fetched via the group messages endpoint
    if the user clicks through.
    """

    group_id = serializers.IntegerField(source="message.group_id", read_only=True)
    message_id = serializers.IntegerField(read_only=True)
    message_text = serializers.SerializerMethodField()
    sender_user_id = serializers.IntegerField(source="message.sender_user_id", read_only=True)
    sender_name = serializers.CharField(source="message.sender_user.get_full_name", read_only=True)
    sent_at = serializers.DateTimeField(source="message.sent_at", read_only=True)

    class Meta:
        model = MessageMention
        fields = [
            "id",
            "group_id",
            "message_id",
            "message_text",
            "sender_user_id",
            "sender_name",
            "sent_at",
            "created_at",
            "read_at",
        ]
        read_only_fields = fields

    def get_message_text(self, obj):
        # Soft-deleted parent messages mustn't leak their text through
        # the mentions inbox either — mirror ReplyToSerializer's policy.
        if obj.message.deleted_at is not None:
            return None
        return obj.message.message_text


class MessageUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        # Intentionally excludes ``reply_to_id``: once a quoted reply is
        # created, its parent context is immutable. Re-pointing a reply
        # via PATCH would let a moderator re-frame an existing message
        # against a different parent, which is not a flow we want to
        # allow. If a "change parent" feature is ever needed, give it a
        # dedicated endpoint with its own audit trail.
        model = Messages
        fields = ["message_text"]

    def validate_message_text(self, value):
        return sanitize_text(value)

    def update(self, instance, validated_data):
        from django.utils import timezone
        instance.message_text = validated_data.get("message_text", instance.message_text)
        instance.edited_at = timezone.now()
        instance.save(update_fields=["message_text", "edited_at"])
        return instance


class MessageGifCreateSerializer(serializers.Serializer):
    """Write payload for ``POST .../messages/send-gif/``.

    Caption text is optional but still runs through ``sanitize_text`` so a
    GIF send cannot bypass the chat moderation filter. ``reply_to_id``
    works exactly like the JSON message-create path — same group-scoped,
    soft-delete-aware queryset via :class:`ReplyToIdField`.
    """

    provider = serializers.CharField(max_length=32, required=False, default="tenor")
    provider_id = serializers.CharField(max_length=128)
    gif_url = serializers.URLField(max_length=500)
    preview_url = serializers.URLField(
        max_length=500, required=False, allow_blank=True, default=""
    )
    title = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    message_text = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=True, default=""
    )
    reply_to_id = ReplyToIdField(
        source="reply_to",
        required=False,
        allow_null=True,
    )

    def validate_message_text(self, value):
        return sanitize_text((value or "").strip())
