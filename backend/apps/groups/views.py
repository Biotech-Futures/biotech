from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from .models import Groups, Countries, GroupMembers, Tracks, CountryStates
from .serializers import CountrySerializer, GroupMemberSerializer

# Create your views here.

class CountryViewSet(viewsets.ModelViewSet):
  queryset = Countries.objects.all()
  serializer_class = CountrySerializer
  
  def get_permissions(self):
    # allow read for anybody and only write for admin
    if self.action in ["list", "retrieve"]:
      return [AllowAny()]
    return [IsAdminUser()] # to check if the user has .is_staff flag

class GroupMemberViewSet(viewsets.ModelViewSet):
    queryset = GroupMembers.objects.all()
    serializer_class = GroupMemberSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "by_group"]:
            return [IsAuthenticated()]
        return [IsAdminUser()]
    
    @action(detail=False, methods=['get'], url_path='by-group/(?P<group_id>[^/.]+)')
    def by_group(self, request, group_id=None):
        """Custom action to get members by group ID"""
        members = self.queryset.filter(group_id=group_id)
        serializer = self.get_serializer(members, many=True)
        return Response(serializer.data)