from rest_framework import serializers
from .models import Countries, GroupMembership, Tracks, Groups


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Countries
        fields = ['id', 'country_name']


class GroupMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMembership
        fields = ['id', 'group', 'user', 'membership_role', 'joined_at', 'left_at']
        read_only_fields = ['id', 'joined_at']
<<<<<<< Updated upstream
        validators = []

    def validate(self, attrs):
        group = attrs.get('group', getattr(self.instance, 'group', None))
        user = attrs.get('user', getattr(self.instance, 'user', None))

        if group is not None and user is not None:
            qs = GroupMembership.objects.filter(group=group, user=user, left_at__isnull=True)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'non_field_errors': ['This user is already a member of this group.']
                })
        return attrs
=======
>>>>>>> Stashed changes


class TrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tracks
        fields = ['id', 'track_code', 'state']


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Groups
<<<<<<< Updated upstream
        fields = ['id', 'group_name', 'track', 'created_at', 'deleted_at', 'year_min', 'year_max', 'lead_mentor', 'max_members']
        read_only_fields = ['id', 'created_at', 'deleted_at']
=======
        fields = [
            'id', 'group_name', 'track', 'created_at', 'deleted_at',
            'year_min', 'year_max', 'lead_mentor', 'max_members',
        ]
        read_only_fields = ['id', 'created_at']
>>>>>>> Stashed changes
        validators = []

    def validate(self, attrs):
        track = attrs.get('track', getattr(self.instance, 'track', None))
        group_name = attrs.get('group_name', getattr(self.instance, 'group_name', None))
        deleted_at = attrs.get('deleted_at', getattr(self.instance, 'deleted_at', None))

        if track is not None and group_name and deleted_at is None:
            qs = Groups.objects.filter(track=track, group_name=group_name, deleted_at__isnull=True)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'non_field_errors': ['An active group with this name already exists in this track.']
                })
        return attrs


class BulkUserSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False
    )
