import os
from datetime import date
from uuid import uuid4

from django.core.files.storage import default_storage
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Event, EventRegistration
from .serializers import (
    EventCoverSerializer,
    EventCreateSerializer,
    EventDetailSerializer,
    EventListSerializer,
)


class EventViewSet(viewsets.ModelViewSet):
    """
    Provides CRUD + registration endpoints for program events.
    """

    queryset = Event.objects.all().annotate(
        registration_count=Count("registrations", distinct=True)
    )
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["type"]
    search_fields = ["title", "description", "location"]
    ordering = ["date", "time", "id"]
    http_method_names = ["get", "post", "delete", "put", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return EventListSerializer
        if self.action == "retrieve":
            return EventDetailSerializer
        if self.action in {"create", "update"}:
            return EventCreateSerializer
        if self.action == "update_cover":
            return EventCoverSerializer
        return EventDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        upcoming = self.request.query_params.get("upcoming")
        if upcoming in {"true", "1", "True"}:
            queryset = queryset.filter(date__gte=date.today())

        event_type = self.request.query_params.get("type")
        if event_type:
            queryset = queryset.filter(type=event_type)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        return queryset.order_by(*self.ordering)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer_class = self.get_serializer_class()

        if page is not None:
            serializer = serializer_class(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = serializer_class(queryset, many=True, context={"request": request})
        return Response({"results": serializer.data, "count": queryset.count()})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        if not self._user_is_admin(request.user):
            raise PermissionDenied("Only administrators can create events.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = Event.objects.create(
            title=serializer.validated_data["title"],
            description=serializer.validated_data.get("description", ""),
            long_description=serializer.validated_data.get("long_description", ""),
            date=serializer.validated_data["date"],
            time=serializer.validated_data["time"],
            location=serializer.validated_data["location"],
            type=serializer.validated_data["type"],
            cover_image=serializer.validated_data.get("cover_image"),
            register_link=serializer.validated_data.get("register_link", ""),
            capacity=serializer.validated_data.get("capacity"),
        )
        output_serializer = EventDetailSerializer(event, context={"request": request})
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PUT")

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH")

    def destroy(self, request, *args, **kwargs):
        if not self._user_is_admin(request.user):
            raise PermissionDenied("Only administrators can delete events.")
        return super().destroy(request, *args, **kwargs)

    @action(
        detail=True,
        methods=["post"],
        url_path="register",
    )
    def register(self, request, *args, **kwargs):
        event = self.get_object()
        registration, created = EventRegistration.objects.get_or_create(
            event=event,
            user=request.user,
        )

        if created:
            return Response(
                {"success": True, "message": "Successfully registered"},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"success": False, "message": "Already registered"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(
        detail=True,
        methods=["put"],
        url_path="cover",
        parser_classes=[MultiPartParser, FormParser],
    )
    def update_cover(self, request, *args, **kwargs):
        if not self._user_is_admin(request.user):
            raise PermissionDenied("Only administrators can update cover images.")

        event = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cover_file = serializer.validated_data["coverImage"]
        storage_path = self._build_storage_path("events/covers", cover_file.name)
        stored_path = default_storage.save(storage_path, cover_file)
        cover_url = default_storage.url(stored_path)

        event.cover_image = cover_url
        event.save(update_fields=["cover_image", "updated_at"])

        return Response({"coverImage": cover_url}, status=status.HTTP_200_OK)

    @staticmethod
    def _build_storage_path(prefix: str, filename: str) -> str:
        _, extension = os.path.splitext(filename)
        return f"{prefix}/{uuid4().hex}{extension}"

    @staticmethod
    def _user_is_admin(user) -> bool:
        return getattr(user, "role", "") == "admin" or user.is_staff
