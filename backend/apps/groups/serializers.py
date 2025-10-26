from rest_framework import serializers
from .models import Countries, GroupMembers, Tracks, Groups, get_current_year

class CountrySerializer(serializers.ModelSerializer):
  class Meta:
    model = Countries
    fields = ['id', 'country_name']

class GroupMemberSerializer(serializers.ModelSerializer):
  class Meta:
    model = GroupMembers
    fields = ['id', 'group', 'user']

class TrackSerializer(serializers.ModelSerializer):
  class Meta:
    model = Tracks
    fields = ['id', 'track_name', 'state']

class GroupSerializer(serializers.ModelSerializer):
  class Meta:
    model = Groups
    fields = ['id', 'group_number', 'group_name', 'track', 'cohort_year', 'creation_datetime', 'deleted_flag', 'deleted_datetime'] 
    read_only_fields = ['id', 'creation_datetime', 'deleted_flag', 'deleted_datetime']
    # disable validator for checkconstraint activate group cohort name must be unique
    # rely on custom validator for this - previously raised an issue where deleted_flag was validated on a patch req but since it is readonly, it was dropped, and hence the validate function never got it
    validators = []

  def validate(self, attrs):
    inst = getattr(self, 'instance', None)
    track = attrs.get('track') or getattr(inst, 'track', None)
    cohort = attrs.get('cohort_year') or getattr(inst, 'cohort_year', None)
    if cohort is None:
      cohort = get_current_year()
    name = attrs.get('group_name') or getattr(inst, 'group_name', None)

    if track and cohort and name:
      qs = Groups.objects.filter(
        track=track, group_name=name, cohort_year=cohort, deleted_flag=False # active group
      )
      if inst:
        qs = qs.exclude(pk=inst.pk)
      if qs.exists():
        # not good. throw error
        raise serializers.ValidationError(
          {"non_field_errors": [f"an active group with this name already exists in {cohort}: {track}."]}
        )
    return attrs
  
  
  def update(self, instance, validated_data):
    # to make group_number immutable after creation
    if 'group_number' in validated_data and instance.group_number:
      if validated_data['group_number'] != instance.group_number:
        raise serializers.ValidationError(
          {"group_number": "group number cannot be changed once set."}
        )
    return super().update(instance, validated_data)

# groups digest
# """
# teachers uploading a file is student registration. possible that the user would already exist, but usually they are new.
# we need to check if a user with that email already exists, and if so, switch to updating the existing profile instead of making a new one

# a student can register a group but only 1.

# both teachers and students can register groups of students.

# groups are usually made in bulk, but it is possible for this to change.

# if (while deleted) another active group took the same name in the same track and cohort, then restoring should fail until the name is changed
# """


class AddGroupMembersSerializer(serializers.Serializer):
  """Input contract for adding members to a group.

  Accepts either user_ids (primary keys) or user_emails (case-insensitive).
  At least one of the two lists must be present. Empty lists are allowed so long as the other is provided.
  """
  user_ids = serializers.ListField(
    child=serializers.IntegerField(min_value=1), required=False, allow_empty=True
  )
  user_emails = serializers.ListField(
    child=serializers.EmailField(), required=False, allow_empty=True
  )
  # Reserved for future behavior tuning (e.g., whether to treat existing links as success/warning)
  ignore_existing = serializers.BooleanField(required=False, default=True)

  def validate(self, data):
    ids = data.get('user_ids') or []
    emails = data.get('user_emails') or []
    if not ids and not emails:
      raise serializers.ValidationError("Provide user_ids or user_emails.")
    return data
