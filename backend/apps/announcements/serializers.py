from rest_framework import serializers

from .models import Announcement, AnnouncementAudience


class AnnouncementAudienceSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.role_name", read_only=True)
    track_name = serializers.CharField(source="track.track_name", read_only=True)

    class Meta:
        model = AnnouncementAudience
        fields = ["id", "role", "role_name", "track", "track_name"]


class AnnouncementAudienceWriteSerializer(serializers.Serializer):
    role_id = serializers.IntegerField(required=False)
    track_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if not attrs.get("role_id") and not attrs.get("track_id"):
            raise serializers.ValidationError("Each audience rule must include role_id or track_id.")
        return attrs


class AnnouncementSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="author_user.email", read_only=True)
    audiences = AnnouncementAudienceSerializer(many=True, read_only=True)
    audience_rules = AnnouncementAudienceWriteSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "author_user",
            "author_email",
            "track",
            "title",
            "body",
            "visibility_scope",
            "published_at",
            "archived_at",
            "audiences",
            "audience_rules",
        ]
        read_only_fields = ["id", "author_user", "published_at", "audiences"]

    def _replace_audiences(self, announcement, audience_rules):
        if audience_rules is None:
            return
        announcement.audiences.all().delete()
        for rule in audience_rules:
            AnnouncementAudience.objects.create(
                announcement=announcement,
                role_id=rule.get("role_id"),
                track_id=rule.get("track_id"),
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
