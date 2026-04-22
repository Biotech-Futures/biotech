from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Countries, GroupMembership, Tracks, Groups
from apps.users.models import User


# Added (#3): explicit schema shape for the lead_user nested object so that drf-spectacular
# renders a full object definition rather than a generic "string" or "{}".
class LeadUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Countries
        fields = ['id', 'country_name']


class GroupMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMembership
        fields = ['id', 'group', 'user', 'membership_role', 'joined_at', 'left_at']
        read_only_fields = ['id', 'joined_at', 'left_at']
        validators = []

    def validate(self, attrs):
        group = attrs.get('group', getattr(self.instance, 'group', None))
        user = attrs.get('user', getattr(self.instance, 'user', None))
        left_at = attrs.get('left_at', getattr(self.instance, 'left_at', None))

        if group is not None and user is not None and left_at is None:
            qs = GroupMembership.objects.filter(group=group, user=user, left_at__isnull=True)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'non_field_errors': ['An active membership for this user already exists in this group.']
                })
        return attrs


class TrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tracks
        fields = ['id', 'track_name', 'state']


class GroupSerializer(serializers.ModelSerializer):
    # Added (#3): the dashboard previously needed three separate requests
    # (GET /groups/groups/, GET /groups/group-members/, GET /groups/tracks/) and still
    # could not display a mentor name because group-members only returned a user ID.
    # These four fields collapse those round-trips into a single groups response.
    track_name = serializers.CharField(source='track.track_name', read_only=True)
    member_count = serializers.SerializerMethodField()
    lead_name = serializers.SerializerMethodField()
    lead_user = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    def _get_mentor_membership(self, obj):
        """Return the first active mentor membership, using the prefetch when available.

        GroupViewSet.get_queryset() attaches a `mentor_memberships` list via Prefetch,
        so the common list/retrieve path costs zero extra queries. The fallback live query
        handles any code path that calls the serializer without the prefetch (e.g. tests,
        admin, or write actions).
        """
        if hasattr(obj, 'mentor_memberships'):
            memberships = obj.mentor_memberships
            return memberships[0] if memberships else None
        return (
            obj.groupmembership_set
            .filter(membership_role__iexact='mentor', left_at__isnull=True)
            .select_related('user')
            .first()
        )

    @extend_schema_field(serializers.IntegerField())
    def get_member_count(self, obj):
        # Reads the `member_count` annotation added by GroupViewSet.get_queryset()
        # when available; falls back to a live count for non-annotated paths.
        if hasattr(obj, 'member_count'):
            return obj.member_count
        return obj.groupmembership_set.filter(left_at__isnull=True).count()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_lead_name(self, obj):
        membership = self._get_mentor_membership(obj)
        if membership:
            user = membership.user
            return f"{user.first_name} {user.last_name}".strip() or None
        return None

    @extend_schema_field(LeadUserSerializer(allow_null=True))
    def get_lead_user(self, obj):
        membership = self._get_mentor_membership(obj)
        if membership:
            user = membership.user
            return {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'role': 'Mentor',
            }
        return None

    @extend_schema_field(serializers.ChoiceField(choices=['active', 'deleted']))
    def get_status(self, obj):
        return 'active' if obj.deleted_at is None else 'deleted'

    class Meta:
        model = Groups
        fields = [
            'id', 'group_name', 'track', 'track_name',
            'created_at', 'deleted_at',
            'member_count', 'lead_name', 'lead_user', 'status',
        ]
        read_only_fields = [
            'id', 'created_at', 'deleted_at',
            'track_name', 'member_count', 'lead_name', 'lead_user', 'status',
        ]
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
        allow_empty=False,
    )


class BulkGroupCreateItemSerializer(serializers.Serializer):
    group_name = serializers.CharField(max_length=255)
    track = serializers.PrimaryKeyRelatedField(queryset=Tracks.objects.all())
    member_user_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=User.objects.all()),
        required=False,
        allow_empty=True,
    )
    mentor_user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )


class BulkGroupCreateSerializer(serializers.Serializer):
    groups = BulkGroupCreateItemSerializer(many=True, allow_empty=False)


class MentorAssignmentSerializer(serializers.Serializer):
    mentor_user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
