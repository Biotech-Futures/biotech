import os
from uuid import uuid4

from django.core.files.storage import default_storage
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Resource
from .serializers import (
    ResourceCreateSerializer,
    ResourceCoverSerializer,
    ResourceDetailSerializer,
    ResourceListSerializer,
)


class ResourceViewSet(viewsets.ModelViewSet):
    """
    Provides CRUD endpoints for managing resources within the library.
    Read access is available to all authenticated users, while write
    operations are limited to admin users.
    """

    queryset = Resource.objects.all()
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["type", "role"]
    search_fields = ["title", "description"]
    http_method_names = ["get", "post", "delete", "put", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return ResourceListSerializer
        if self.action == "retrieve":
            return ResourceDetailSerializer
        if self.action == "create":
            return ResourceCreateSerializer
        if self.action == "update_cover":
            return ResourceCoverSerializer
        return ResourceDetailSerializer

    def get_queryset(self):
        """
        Restrict resources based on the current user's role, unless they
        are an administrator.
        """
        queryset = super().get_queryset()
        user = self.request.user

        if not user.is_authenticated:
            return queryset.none()

        if self._user_is_admin(user):
            return queryset

        user_role = getattr(user, "role", Resource.ROLE_ALL)
        return queryset.filter(Q(role=Resource.ROLE_ALL) | Q(role=user_role))

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({"results": serializer.data, "count": queryset.count()})

    def create(self, request, *args, **kwargs):
        if not self._user_is_admin(request.user):
            raise PermissionDenied("Only administrators can upload resources.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        storage_path = self._build_storage_path("resources/files", uploaded_file.name)
        stored_path = default_storage.save(storage_path, uploaded_file)
        file_url = default_storage.url(stored_path)

        resource = Resource.objects.create(
            title=serializer.validated_data["title"],
            description=serializer.validated_data.get("description", ""),
            type=serializer.validated_data["type"],
            role=serializer.validated_data["role"],
            file_url=file_url,
        )

        output_serializer = ResourceDetailSerializer(resource)
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        if not self._user_is_admin(request.user):
            raise PermissionDenied("Only administrators can delete resources.")
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PUT")

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH")

    @action(
        detail=True,
        methods=["put"],
        url_path="cover",
        parser_classes=[MultiPartParser, FormParser],
    )
    def update_cover(self, request, *args, **kwargs):
        if not self._user_is_admin(request.user):
            raise PermissionDenied("Only administrators can update cover images.")

        resource = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cover_file = serializer.validated_data["coverImage"]
        storage_path = self._build_storage_path("resources/covers", cover_file.name)
        stored_path = default_storage.save(storage_path, cover_file)
        cover_url = default_storage.url(stored_path)

        resource.cover_image = cover_url
        resource.save(update_fields=["cover_image", "updated_at"])

        return Response({"coverImage": cover_url}, status=status.HTTP_200_OK)

    @staticmethod
    def _build_storage_path(prefix: str, filename: str) -> str:
        _, extension = os.path.splitext(filename)
        return f"{prefix}/{uuid4().hex}{extension}"

    @staticmethod
    def _user_is_admin(user) -> bool:
        return getattr(user, "role", "") == Resource.ROLE_ADMIN or user.is_staff
