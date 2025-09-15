from rest_framework import serializers
from .models import Countries, GroupMembers

class CountrySerializer(serializers.ModelSerializer):
  class Meta:
    model = Countries
    fields = ['id', 'country_name']

class GroupMemberSerializer(serializers.ModelSerializer):
  class Meta:
    model = GroupMembers
    fields = ['id', 'group', 'user']