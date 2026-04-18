from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from .models import Groups, Countries, GroupMembership, Tracks
from .serializers import CountrySerializer, GroupMembershipSerializer, TrackSerializer, GroupSerializer


class CountryViewSet(viewsets.ModelViewSet):
    queryset = Countries.objects.order_by("country_name")
    serializer_class = CountrySerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAdminUser()]


class GroupMemberViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMembershipSerializer

    def get_queryset(self):
        return GroupMembership.objects.select_related("group", "user").order_by("id")

    def get_permissions(self):
        if self.action in ["list", "retrieve", "by_group"]:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='by-group/(?P<group_id>[^/.]+)')
    def by_group(self, request, group_id=None):
        members = self.get_queryset().filter(group_id=group_id)
        serializer = self.get_serializer(members, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrackViewSet(viewsets.ModelViewSet):
    queryset = Tracks.objects.order_by("track_code", "id")
    serializer_class = TrackSerializer
    http_method_names = ["get", "post", "put", "patch"]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ["track_code", "id"]
    search_fields = ["track_code"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAdminUser()]


class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer

    def get_queryset(self):
        raw = (self.request.query_params.get('include_deleted') or '').lower().strip()
        if raw == 'true' and self.request.user.is_staff:
            return Groups.objects.order_by("group_name", "id")
        return Groups.objects.filter(deleted_at__isnull=True).order_by("group_name", "id")

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        if group.deleted_at is not None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        group.deleted_at = timezone.now()
        group.save(update_fields=["deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
