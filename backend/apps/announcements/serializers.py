from textwrap import shorten

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
    author_name = serializers.SerializerMethodField()
    track_name = serializers.CharField(source="track.track_name", read_only=True, allow_null=True)
    summary = serializers.SerializerMethodField()
    audience_summary = serializers.SerializerMethodField()
    audience_labels = serializers.SerializerMethodField()
    is_archived = serializers.SerializerMethodField()
    audiences = AnnouncementAudienceSerializer(many=True, read_only=True)
    audience_rules = AnnouncementAudienceWriteSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "author_user",
            "author_email",
            "author_name",
            "track",
            "track_name",
            "title",
            "body",
            "summary",
            "visibility_scope",
            "published_at",
            "archived_at",
            "is_archived",
            "audience_summary",
            "audience_labels",
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

    def get_author_name(self, obj):
        if not obj.author_user_id or obj.author_user is None:
            return None
        return obj.author_user.get_full_name().strip() or obj.author_user.email

    def get_summary(self, obj):
        # Provide a stable short form so list UIs do not have to invent their own truncation logic.
        return shorten((obj.body or "").replace("\n", " "), width=180, placeholder="...")

    def get_audience_summary(self, obj):
        if obj.visibility_scope == Announcement.VisibilityScope.PUBLIC:
            return "all"

        role_labels = [rule.role.role_name.lower() for rule in obj.audiences.all() if rule.role_id and rule.role]
        track_labels = [rule.track.track_name for rule in obj.audiences.all() if rule.track_id and rule.track]

        if len(role_labels) == 1 and not track_labels and not obj.track_id:
            return role_labels[0]
        if not role_labels and (track_labels or obj.track_id):
            return "track"
        if role_labels or track_labels:
            return "scoped"
        return obj.visibility_scope

    def get_audience_labels(self, obj):
        labels = []
        if obj.track_id and obj.track is not None:
            labels.append(f"track:{obj.track.track_name}")
        for rule in obj.audiences.all():
            if rule.role_id and rule.role is not None:
                labels.append(rule.role.role_name)
            if rule.track_id and rule.track is not None:
                labels.append(f"track:{rule.track.track_name}")
        return labels

    def get_is_archived(self, obj):
        return obj.archived_at is not None
