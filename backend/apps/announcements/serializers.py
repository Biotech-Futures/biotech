from rest_framework import serializers

from .models import Announcement, AnnouncementAudience
from .rendering import fill_merge_tags


def _requesting_user(serializer):
    """The user reading the announcement, when there is one.

    The platform fills an announcement's merge tags (``{{ first_name }}``)
    with the reader's own details. The admin dashboard reads through its own
    API (``apps.admin``), which keeps the body as written so it stays
    editable, so only these serializers fill them."""
    request = serializer.context.get("request")
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    return None


class AnnouncementAudienceSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.role_name", read_only=True)
    group_name = serializers.CharField(source="group.group_name", read_only=True)

    class Meta:
        model = AnnouncementAudience
        fields = ["id", "role", "role_name", "group", "group_name"]


class AnnouncementAudienceWriteSerializer(serializers.Serializer):
    role_id = serializers.IntegerField(required=False)
    group_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if not attrs.get("role_id") and not attrs.get("group_id"):
            raise serializers.ValidationError(
                "Each audience rule must include role_id or group_id."
            )
        return attrs


class AnnouncementSerializer(serializers.ModelSerializer):
    # Authors are masked on the public API: every announcement surfaces as
    # "Administrator" regardless of which admin sent it. The real
    # ``author_user`` FK still exists on the model for audit/filter use;
    # the admin dashboard (apps.admin) has its own serializer that exposes it.
    sender_name = serializers.CharField(default="Administrator", read_only=True)
    audiences = AnnouncementAudienceSerializer(many=True, read_only=True)
    audience_rules = AnnouncementAudienceWriteSerializer(many=True, write_only=True, required=False)
    # Not yet opened by the user reading it, and not their own: shows as New.
    is_new = serializers.SerializerMethodField()

    # Above this size we truncate on list responses; one embedded base64
    # image in a single row otherwise inflates the whole page payload.
    LIST_BODY_CAP = 4096

    class Meta:
        model = Announcement
        fields = [
            "id",
            "sender_name",
            "title",
            "body",
            "visibility_scope",
            "published_at",
            "archived_at",
            "audiences",
            "audience_rules",
            "is_new",
        ]
        read_only_fields = ["id", "published_at", "audiences", "is_new"]

    def get_is_new(self, obj) -> bool:
        user = _requesting_user(self)
        # Without the queryset's seen_by_me (a write's response), never New;
        # nor one from before New existed.
        if user is None or not obj.shows_new or getattr(obj, "seen_by_me", True):
            return False
        return obj.author_user_id != user.id

    def _replace_audiences(self, announcement, audience_rules):
        if audience_rules is None:
            return
        announcement.audiences.all().delete()
        for rule in audience_rules:
            AnnouncementAudience.objects.create(
                announcement=announcement,
                role_id=rule.get("role_id"),
                group_id=rule.get("group_id"),
            )

    def create(self, validated_data):
        audience_rules = validated_data.pop("audience_rules", [])
        announcement = super().create(validated_data)
        self._replace_audiences(announcement, audience_rules)
        return announcement

    def update(self, instance, validated_data):
        audience_rules = validated_data.pop("audience_rules", None)
        announcement = super().update(instance, validated_data)
        self._replace_audiences(announcement, audience_rules)
        return announcement

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = _requesting_user(self)
        if user is not None and data.get("body"):
            data["body"] = fill_merge_tags(data["body"], user)
        return data


class AnnouncementListSerializer(AnnouncementSerializer):
    """Truncates ``body`` for list responses.

    A single base64-embedded image in one announcement can otherwise push
    the list payload past 300 KB. Detail endpoints keep returning the full
    body so the dedicated detail view still shows everything.
    """

    body = serializers.SerializerMethodField()
    body_truncated = serializers.SerializerMethodField()

    class Meta(AnnouncementSerializer.Meta):
        fields = AnnouncementSerializer.Meta.fields + ["body_truncated"]

    def get_body(self, obj):
        # Fill before truncating, so a cut can never leave half a tag behind.
        body = fill_merge_tags(obj.body or "", _requesting_user(self))
        if len(body) <= self.LIST_BODY_CAP:
            return body
        return body[: self.LIST_BODY_CAP]

    def get_body_truncated(self, obj):
        return len(obj.body or "") > self.LIST_BODY_CAP
