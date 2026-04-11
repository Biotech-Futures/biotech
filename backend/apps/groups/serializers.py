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
    fields = [
        'id', 'group_name', 'track', 'creation_datetime', 'deleted_flag', 'deleted_datetime',
        'year_min', 'year_max', 'lead_mentor', 'max_members',
    ]
    read_only_fields = ['id', 'creation_datetime', 'deleted_flag', 'deleted_datetime']


# for bulk endpoints, rejects empty lists + non-positive integers
class BulkUserSerializer(serializers.Serializer):
  user_ids = serializers.ListField(
    child=serializers.IntegerField(min_value=1),
    allow_empty=False
  )
