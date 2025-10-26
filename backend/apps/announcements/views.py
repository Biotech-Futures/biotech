from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Announcement
from .serializers import AnnouncementCreateSerializer, AnnouncementSerializer


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    Provides list/detail/create endpoints for announcements.
    """

    queryset = Announcement.objects.all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]
    filterset_fields = ["audience"]
    search_fields = ["title", "summary", "content", "author"]

    def get_serializer_class(self):
        if self.action == "create":
            return AnnouncementCreateSerializer
        return AnnouncementSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.request

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(summary__icontains=search) | Q(content__icontains=search)
            )

        user = request.user
        user_role = getattr(user, "role", Announcement.AUDIENCE_ALL)
        if user_role == Announcement.AUDIENCE_ADMIN or user.is_staff:
            # Admins can see all announcements regardless of audience
            return queryset

        queryset = queryset.filter(audience__in=[Announcement.AUDIENCE_ALL, user_role])

        return queryset.order_by("-created_at", "-id")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer_class = self.get_serializer_class()

        if page is not None:
            serializer = serializer_class(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = serializer_class(queryset, many=True)
        return Response({"results": serializer.data, "count": queryset.count()})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        if not self._user_is_admin(request.user):
            return Response(
                {"error": "Only administrators can create announcements."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = Announcement.objects.create(**serializer.validated_data)
        output_serializer = AnnouncementSerializer(announcement)
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        if not self._user_is_admin(request.user):
            return Response(
                {"error": "Only administrators can delete announcements."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @staticmethod
    def _user_is_admin(user) -> bool:
        return getattr(user, "role", "") == "admin" or user.is_staff
