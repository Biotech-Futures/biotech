from rest_framework import serializers
from .models import Countries, GroupMembership, Groups
from apps.users.models import User


class CountrySerializer(serializers.ModelSerializer):
  class Meta:
    model = Countries
    fields = ['id', 'country_name']


class GroupMembershipSerializer(serializers.ModelSerializer):
  user_name = serializers.SerializerMethodField()

  class Meta:
    model = GroupMembership
    fields = ['id', 'group', 'user', 'user_name', 'membership_role', 'joined_at', 'left_at']
    read_only_fields = ['id', 'user_name', 'joined_at', 'left_at']
    validators = []

  def get_user_name(self, obj) -> str | None:
    user = obj.user
    if user is None:
      return None
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email

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


class GroupSerializer(serializers.ModelSerializer):
  class Meta:
    model = Groups
    fields = ['id', 'group_name', 'created_at', 'deleted_at']
    read_only_fields = ['id', 'created_at', 'deleted_at']
    validators = []
    # Suppress the auto-derived field-level UniqueValidator so the duplicate-name
    # check flows through validate() and surfaces as non_field_errors (the shape
    # the frontend expects), not a group_name field error.
    # Optional on write: a blank name means "auto-generate BTF<n>" (see perform_create).
    extra_kwargs = {
      'group_name': {'validators': [], 'required': False, 'allow_blank': True},
    }

  def validate(self, attrs):
    # required=False/allow_blank exist for the create auto-name path only; on update
    # they would otherwise let a blank name through to the DB check constraint (500).
    if self.instance is not None:
      if not self.partial and 'group_name' not in attrs:
        raise serializers.ValidationError({'group_name': ['This field is required.']})
      if 'group_name' in attrs and not attrs['group_name'].strip():
        raise serializers.ValidationError({'group_name': ['This field may not be blank.']})

    group_name = attrs.get('group_name', getattr(self.instance, 'group_name', None))
    deleted_at = attrs.get('deleted_at', getattr(self.instance, 'deleted_at', None))

    if group_name and deleted_at is None:
      qs = Groups.objects.filter(group_name=group_name, deleted_at__isnull=True)
      if self.instance is not None:
        qs = qs.exclude(pk=self.instance.pk)
      if qs.exists():
        raise serializers.ValidationError({
          'non_field_errors': ['An active group with this name already exists.']
        })
    return attrs


class BulkUserSerializer(serializers.Serializer):
  user_ids = serializers.ListField(
    child=serializers.IntegerField(min_value=1),
    allow_empty=False
  )


class BulkGroupCreateItemSerializer(serializers.Serializer):
  # Blank means "auto-generate BTF<n>", matching the single-create path.
  group_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
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
