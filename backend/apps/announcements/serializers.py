from rest_framework import serializers

from .models import Announcement, AnnouncementAudience


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
        ]
        read_only_fields = ["id", "published_at", "audiences"]

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
        body = obj.body or ""
        if len(body) <= self.LIST_BODY_CAP:
            return body
        return body[: self.LIST_BODY_CAP]

    def get_body_truncated(self, obj):
        return len(obj.body or "") > self.LIST_BODY_CAP
