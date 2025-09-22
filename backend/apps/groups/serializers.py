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
    fields = ['id', 'group_number', 'group_name', 'track', 'creation_datetime', 'deleted_flag', 'deleted_datetime'] 
    read_only_fields = ['id', 'creation_datetime', 'deleted_flag', 'deleted_datetime']
  
  def update(self, instance, validated_data):
    # to make group_number immutable after creation
    if 'group_number' in validated_data and instance.group_number:
      if validated_data['group_number'] != instance.group_number:
        raise serializers.ValidationError(
          {"group_number": "group number cannot be changed once set."}
        )
    return super().update(instance, validated_data)


# for bulk endpoints, rejects empty lists + non-positive integers
class BulkUserSerializer(serializers.Serializer):
  user_ids = serializers.ListField(
    child=serializers.IntegerField(min_value=1),
    allow_empty=False
  )
