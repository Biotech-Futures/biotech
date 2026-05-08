# Phase 2 update: updated serializers to reflect new Messages model fields.
# Added is_deleted, is_edited as read-only fields.
# Added MessageUpdateSerializer for edit operations that sets edited_at automatically.
# Added MessageStatusSerializer for read/delivery tracking.

from rest_framework import serializers
from .models import Messages, MessageResource, MessageStatus
from .utils import sanitize_text
from apps.resources.models import Resources


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


class MessageStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageStatus
        fields = ["id", "user", "status", "delivered_at", "read_at"]
        read_only_fields = ["id", "delivered_at", "read_at"]


class ReplyToSerializer(serializers.ModelSerializer):
    """Lightweight, *non-recursive* projection of a parent message used to
    embed quoted-reply context inside a child message's payload.

    Field-naming choice
    -------------------
    This serializer deliberately uses the short keys ``text`` and
    ``user_id`` instead of the parent ``MessageSerializer``'s
    ``message_text`` / ``sender_user_id``. The nested object is rendered
    inside chat bubbles, where the FE strongly benefits from a compact
    shape; the full schema remains available on the *child* message
    itself. This is a deliberate UI-affordance projection, not a missed
    consistency.

    Soft-deleted parents
    --------------------
    If the parent has been moderated away (``deleted_at`` is not null),
    the embedded payload still surfaces ``id`` and ``user_id`` (so the
    FE can render an attribution placeholder like
    ``"\u21b3 deleted message from <user>"``) but **omits the text**:
    ``text`` is nulled and the explicit boolean ``deleted: true`` is
    set. This prevents soft-deleted content from leaking through every
    child message that quoted it.

    Recursion bound
    ---------------
    The serializer does **not** itself include a ``reply_to`` field, so
    the response is flat at exactly one level of nesting no matter how
    deep the underlying chain of quoted replies is. That is the
    structural recursion guard for the API (see
    ``test_reply_to_nesting_serialization``).
    """

    text = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source="sender_user_id", read_only=True)
    deleted = serializers.SerializerMethodField()

    class Meta:
        model = Messages
        fields = ["id", "text", "user_id", "deleted"]
        read_only_fields = fields

    def get_text(self, obj):
        # Soft-deleted parents do not expose their content. The id +
        # user_id remain so the FE can still render an attribution
        # placeholder.
        if obj.deleted_at is not None:
            return None
        return obj.message_text

    def get_deleted(self, obj):
        return obj.deleted_at is not None


class ReplyToIdField(serializers.PrimaryKeyRelatedField):
    """Write-side companion to :class:`ReplyToSerializer`.

    The queryset is restricted to the **current group's non-deleted
    messages**. This consolidates two invariants into the canonical
    DRF place (the field's queryset) so they cannot drift:

    * Cross-group leak: a reply in group A cannot point at a parent in
      group B \u2014 such a PK is simply not in the queryset, so DRF
      rejects with the standard ``"Invalid pk \\"X\\" - object does not
      exist."`` error. The generic message is also a small security
      win: it does not leak the existence of messages in other groups.
    * Soft-deleted parents: a reply cannot point at a moderated-away
      parent on creation. Same standard 400.

    Fail-closed: if the serializer is ever instantiated outside a view
    (management command, signal handler, future bulk import) the
    queryset is empty, so any ``reply_to_id`` is rejected. The previous
    implementation read the group from ``self.context["view"].kwargs``
    and silently *skipped* the cross-group check when context was
    missing \u2014 the opposite of what this validator should do.
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
    sender_name = serializers.CharField(
        source="sender_user.get_full_name", read_only=True
    )
    is_deleted = serializers.BooleanField(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)

    # Read: nested lightweight parent context (or null if not a reply).
    # Write: ``reply_to_id`` accepts a PK constrained to the current
    # group's non-deleted messages \u2014 see ``ReplyToIdField``.
    reply_to = ReplyToSerializer(read_only=True)
    reply_to_id = ReplyToIdField(
        source="reply_to",
        write_only=True,
        required=False,
        allow_null=True,
    )

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
            "resources",
            "reply_to",
            "reply_to_id",
        ]
        read_only_fields = [
            "id", "group", "sender_user",
            "sent_at", "edited_at", "deleted_at",
        ]

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
        if not msg and not resources_data:
            raise serializers.ValidationError(
                "Message must include text or at least one resource."
            )
        # Sanitise BEFORE serializer.save() so the moderated text is what
        # gets persisted. Doing this here keeps the rule decoupled from
        # the view and ensures every write path (REST POST, future bulk
        # imports, admin tools) goes through the same filter.
        if "message_text" in attrs:
            attrs["message_text"] = sanitize_text(attrs["message_text"])
        # Cross-group + soft-delete invariants on ``reply_to_id`` are
        # enforced inside :class:`ReplyToIdField` itself \u2014 see its
        # ``get_queryset`` \u2014 so this validator does not need to
        # re-check them. Pushing the check into the field also ensures
        # any future serializer that reuses ``ReplyToIdField`` inherits
        # the same protection automatically.
        return attrs


class MessageUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Messages
        # Intentionally excludes ``reply_to_id``: once a quoted reply is
        # created, its parent context is immutable. Re-pointing a reply
        # via PATCH would let a moderator re-frame an existing message
        # against a different parent, which is not a flow we want to
        # allow. If a "change parent" feature is ever needed, give it a
        # dedicated endpoint with its own audit trail.
        fields = ["message_text"]

    def validate_message_text(self, value):
        return sanitize_text(value)

    def update(self, instance, validated_data):
        from django.utils import timezone
        instance.message_text = validated_data.get("message_text", instance.message_text)
        instance.edited_at = timezone.now()
        instance.save(update_fields=["message_text", "edited_at"])
        return instance