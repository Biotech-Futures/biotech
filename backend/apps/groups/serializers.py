from rest_framework import serializers
from .models import Countries, GroupMembership, Tracks, Groups
from apps.users.models import User


class CountrySerializer(serializers.ModelSerializer):
  class Meta:
    model = Countries
    fields = ['id', 'country_name']


class GroupMembershipSerializer(serializers.ModelSerializer):
  # Read-only display label for chat mention autocomplete and member lists.
  # Mentions on the wire still use the numeric user id (``<@user_id>``);
  # this field only powers the UI label so the frontend doesn't have to
  # fall back to "User 60". Falls through gracefully when names are missing.
  user_name = serializers.SerializerMethodField(read_only=True)

  class Meta:
    model = GroupMembership
    fields = ['id', 'group', 'user', 'user_name', 'membership_role', 'joined_at', 'left_at']
    read_only_fields = ['id', 'user_name', 'joined_at', 'left_at']
    validators = []

  def get_user_name(self, obj) -> str:
    user = getattr(obj, 'user', None)
    if user is None:
      return ''
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    if full_name:
      return full_name
    if user.email:
      return user.email
    return f"User {user.id}"

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
  class Meta:
    model = Groups
    fields = ['id', 'group_name', 'track', 'created_at', 'deleted_at']
    read_only_fields = ['id', 'created_at', 'deleted_at']
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
