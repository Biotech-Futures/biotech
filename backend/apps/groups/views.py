from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from .models import Groups, Countries, GroupMembers, Tracks, CountryStates
from .serializers import CountrySerializer, GroupMemberSerializer, TrackSerializer, GroupSerializer

# Create your views here.

User = get_user_model()

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
    
    #TODO: expand by addung endpoints to implement logic of adding and removing members
    
class TrackViewSet(viewsets.ModelViewSet):
    queryset = Tracks.objects.all()
    serializer_class = TrackSerializer
    http_method_names = ['get', 'post', 'put', 'patch'] # disable delete 
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['track_name', 'id']
    search_fields = ['track_name']

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAdminUser()]
    
class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    lookup_field = "group_number" # we will look up with groups/R_12skjXJde/ instead of groups/12/

    # by default, don't include the deleted flags. only show if include_deleted in query param
    def get_queryset(self):
        raw = (self.request.query_params.get('include_deleted') or '').lower().strip()
        if raw == 'true' and self.request.user.is_staff:
            return Groups.objects.all()
        return Groups.objects.filter(deleted_flag=False)
    
    # read for authenticated and write for authorised
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        if group.deleted_flag:
            # means group is alr deleted but no errors
            return Response(status=status.HTTP_204_NO_CONTENT)
        group.deleted_flag = True
        group.deleted_datetime = timezone.now()
        group.save(update_fields=['deleted_flag', 'deleted_datetime'])
        return Response(status=status.HTTP_204_NO_CONTENT)
    


        

"""
GET /groups/ - list groups
POST /groups/ - create group
GET /groups/{id} - retrieve group
PUT/PATCH /groups/{id} - update a group

maybe look into these custom actions
GET /groups/{id}/members - list members in a group?
POST /groups/{id}/add-members/ - bulk add using user_id
POST /groups/{id}/remove-members/ - bulk remove members using user id
and optional soft delete: DELETE /groups/{id} - to set deleted_flag=True
"""