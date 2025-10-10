from rest_framework import serializers
from .models import Countries, GroupMembers, Tracks, Groups

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

  def validate(self, attrs):
    inst = getattr(self, 'instance', None)
    track = attrs.get('track') or getattr(inst, 'track', None)
    cohort = attrs.get('cohort_year') or getattr(inst, 'cohort_year', None)
    name = attrs.get('group_name') or getattr(inst, 'group_name', None)

    if track and cohort and name:
      qs = Groups.objects.filter(
        track=track, group_name=name, cohort_year=cohort, deleted_flag=False #active group
      )
      if inst:
        qs = qs.exclude(pk=inst.pk)
      if qs.exists():
        # not good. throw error
        raise serializers.ValidationError(
          {"group_name": f"an active group with this name already exists in {cohort}: {track}."}
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
