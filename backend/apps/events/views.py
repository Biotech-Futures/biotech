from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.resources.models import RoleAssignmentHistory
from apps.users.models import User

from .models import EventRsvp, Events
from .serializers import (
    EventCurrentUserRsvpSerializer,
    EventRsvpRequestSerializer,
    EventRsvpSerializer,
    EventRsvpUpsertSerializer,
    EventSerializer,
)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class EventViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Events.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        now = timezone.now()
        queryset = (
            Events.objects.filter(deleted_at__isnull=True)
            .select_related("track", "host_user")
            .annotate(
                pending_rsvp_count=Count("rsvps", filter=Q(rsvps__rsvp_status=EventRsvp.RsvpStatus.PENDING)),
                going_rsvp_count=Count("rsvps", filter=Q(rsvps__rsvp_status=EventRsvp.RsvpStatus.GOING)),
                maybe_rsvp_count=Count("rsvps", filter=Q(rsvps__rsvp_status=EventRsvp.RsvpStatus.MAYBE)),
                declined_rsvp_count=Count("rsvps", filter=Q(rsvps__rsvp_status=EventRsvp.RsvpStatus.DECLINED)),
                rsvp_total_count=Count("rsvps"),
            )
        )

        include_past = str(self.request.query_params.get("include_past", "")).lower() in {"1", "true", "yes"}
        if not include_past:
            queryset = queryset.filter(ends_datetime__gte=now)

        q = self.request.query_params.get("q")
        if q:
            queryset = queryset.filter(
                Q(event_name__icontains=q.strip())
                | Q(description__icontains=q.strip())
                | Q(location__icontains=q.strip())
            )

        track_id = self.request.query_params.get("track_id")
        if track_id:
            queryset = queryset.filter(track_id=track_id)

        event_type = self.request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        is_virtual = self.request.query_params.get("is_virtual")
        if is_virtual is not None:
            normalized = str(is_virtual).lower()
            if normalized in {"1", "true", "yes"}:
                queryset = queryset.filter(is_virtual=True)
            elif normalized in {"0", "false", "no"}:
                queryset = queryset.filter(is_virtual=False)

        starts_after = self.request.query_params.get("starts_after")
        if starts_after:
            queryset = queryset.filter(start_datetime__gte=starts_after)

        starts_before = self.request.query_params.get("starts_before")
        if starts_before:
            queryset = queryset.filter(start_datetime__lte=starts_before)

        if self.request.user and self.request.user.is_authenticated:
            # Prefetching only the caller's RSVP keeps event cards SPA-friendly without
            # introducing a second endpoint call per card just to render registration state.
            queryset = queryset.prefetch_related(
                Prefetch(
                    "rsvps",
                    queryset=EventRsvp.objects.filter(user=self.request.user).order_by("id"),
                    to_attr="_current_user_rsvps",
                )
            )

        return queryset.order_by("start_datetime", "id")

    def perform_create(self, serializer):
        event = serializer.save(host_user=self.request.user if self.request.user.is_authenticated else None)
        log_audit_event(
            actor=self.request.user if self.request.user.is_authenticated else None,
            entity_type="event",
            entity_id=event.id,
            action="create",
            after_state=EventSerializer(event).data,
        )

    def perform_update(self, serializer):
        event = self.get_object()
        before_state = EventSerializer(event, context=self.get_serializer_context()).data
        event = serializer.save()
        log_audit_event(
            actor=self.request.user if self.request.user.is_authenticated else None,
            entity_type="event",
            entity_id=event.id,
            action="update",
            before_state=before_state,
            after_state=EventSerializer(event, context=self.get_serializer_context()).data,
        )

    def destroy(self, request, *args, **kwargs):
        event = self.get_object()
        before_state = EventSerializer(event, context=self.get_serializer_context()).data
        event.deleted_at = timezone.now()
        event.save(update_fields=["deleted_at"])
        log_audit_event(
            actor=request.user if request.user.is_authenticated else None,
            entity_type="event",
            entity_id=event.id,
            action="archive",
            before_state=before_state,
            after_state=EventSerializer(event, context=self.get_serializer_context()).data,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class IsNotStudent(permissions.BasePermission):
    def _get_active_role(self, user):
        if not user or not user.is_authenticated:
            return None

        now = timezone.now()
        active_role = (
            RoleAssignmentHistory.objects.filter(user=user, valid_from__lte=now)
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
            .select_related("role")
            .first()
        )
        if active_role and active_role.role:
            return active_role.role.role_name
        return None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff or request.user.is_superuser:
            return True

        role_name = self._get_active_role(request.user)
        if not role_name:
            return False
        return role_name.lower() in {"mentor", "supervisor", "administrator"}


class EventInviteCreateView(APIView):
    permission_classes = [IsNotStudent]

    @extend_schema(
        request=EventRsvpRequestSerializer,
        responses={200: EventRsvpUpsertSerializer},
    )
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        event = get_object_or_404(Events, pk=kwargs.get("id"))
        user = get_object_or_404(User, pk=kwargs.get("uid"))

        rsvp_status = request.data.get("rsvp_status", EventRsvp.RsvpStatus.PENDING)
        responded_at = timezone.now() if rsvp_status != EventRsvp.RsvpStatus.PENDING else None

        rsvp, _ = EventRsvp.objects.update_or_create(
            event=event,
            user=user,
            defaults={
                "rsvp_status": rsvp_status,
                "responded_at": responded_at,
            },
        )
        log_audit_event(
            actor=request.user,
            entity_type="event_rsvp",
            entity_id=rsvp.id,
            action="upsert",
            after_state=EventRsvpSerializer(rsvp).data,
        )
        return Response(EventRsvpUpsertSerializer(rsvp).data, status=status.HTTP_200_OK)


class EventMeRsvpView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=EventRsvpRequestSerializer,
        responses={200: EventCurrentUserRsvpSerializer},
    )
    @transaction.atomic
    def put(self, request, *args, **kwargs):
        event = get_object_or_404(Events, pk=kwargs.get("id"), deleted_at__isnull=True)
        serializer = EventRsvpRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        rsvp_status = serializer.validated_data["rsvp_status"]
        responded_at = timezone.now() if rsvp_status != EventRsvp.RsvpStatus.PENDING else None

        rsvp, _ = EventRsvp.objects.update_or_create(
            event=event,
            user=request.user,
            defaults={
                "rsvp_status": rsvp_status,
                "responded_at": responded_at,
            },
        )
        log_audit_event(
            actor=request.user,
            entity_type="event_rsvp",
            entity_id=rsvp.id,
            action="upsert_self",
            after_state=EventCurrentUserRsvpSerializer(rsvp).data,
        )
        return Response(EventCurrentUserRsvpSerializer(rsvp).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        event = get_object_or_404(Events, pk=kwargs.get("id"), deleted_at__isnull=True)
        rsvp = EventRsvp.objects.filter(event=event, user=request.user).first()
        if rsvp is None:
            return Response(status=status.HTTP_204_NO_CONTENT)

        before_state = EventCurrentUserRsvpSerializer(rsvp).data
        rsvp.delete()
        log_audit_event(
            actor=request.user,
            entity_type="event_rsvp",
            entity_id=before_state["id"],
            action="delete_self",
            before_state=before_state,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventPagePagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class EventInviteListHTMLView(generics.ListAPIView):
    serializer_class = EventRsvpSerializer
    permission_classes = [IsNotStudent]
    pagination_class = EventPagePagination

    def get_queryset(self):
        event = get_object_or_404(Events, pk=self.kwargs.get("id"))
        return EventRsvp.objects.select_related("event", "user").filter(event=event).order_by("id")


class EventInviteListMeHTMLView(generics.ListAPIView):
    serializer_class = EventRsvpSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = EventPagePagination

    def get_queryset(self):
        return EventRsvp.objects.select_related("event", "user").filter(user=self.request.user).order_by("id")
