from rest_framework import serializers
from .models import Countries, GroupMembership, Tracks, Groups


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Countries
        fields = ['id', 'country_name']


class GroupMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMembership
        fields = ["id", "group", "user", "membership_role", "joined_at", "left_at"]
        read_only_fields = ["id", "joined_at"]
        validators = []

    def validate(self, attrs):
        group = attrs.get('group', getattr(self.instance, 'group', None))
        user = attrs.get('user', getattr(self.instance, 'user', None))

        if group is not None and user is not None:
            qs = GroupMembership.objects.filter(group=group, user=user)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'non_field_errors': ['This user is already a member of this group.']
                })
        return attrs


class TrackSerializer(serializers.ModelSerializer):
    track_name = serializers.CharField(source="track_code", max_length=100)

    class Meta:
        model = Tracks
        fields = ["id", "track_name", "state"]


class GroupSerializer(serializers.ModelSerializer):
    creation_datetime = serializers.DateTimeField(source="created_at", read_only=True)
    deleted_flag = serializers.SerializerMethodField()
    deleted_datetime = serializers.DateTimeField(source="deleted_at", read_only=True)

    class Meta:
        model = Groups
        fields = [
            "id",
            "group_name",
            "track",
            "creation_datetime",
            "deleted_flag",
            "deleted_datetime",
        ]
        read_only_fields = ["id", "creation_datetime", "deleted_flag", "deleted_datetime"]
        validators = []

    def get_deleted_flag(self, obj):
        return obj.deleted_at is not None

    def validate(self, attrs):
        track = attrs.get("track", getattr(self.instance, "track", None))
        group_name = attrs.get("group_name", getattr(self.instance, "group_name", None))
        deleted_at = getattr(self.instance, "deleted_at", None) if self.instance else None
        is_active = deleted_at is None

        if track is not None and group_name and is_active:
            qs = Groups.objects.filter(track=track, group_name=group_name, deleted_at__isnull=True)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "An active group with this name already exists in this track."
                        ]
                    }
                )
        return attrs


class BulkUserSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False
    )
