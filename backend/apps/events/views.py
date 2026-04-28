from django.db import transaction
from django.db.models import Q
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
from .serializers import EventRsvpRequestSerializer, EventRsvpSerializer, EventRsvpUpsertSerializer, EventSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            return bool(request.user and request.user.is_staff)
        return True


class EventViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = Events.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        now = timezone.now()
        return Events.objects.filter(deleted_at__isnull=True, ends_datetime__gte=now).order_by("start_datetime")

    def perform_create(self, serializer):
        event = serializer.save(host_user=self.request.user if self.request.user.is_authenticated else None)
        log_audit_event(
            actor=self.request.user if self.request.user.is_authenticated else None,
            entity_type="event",
            entity_id=event.id,
            action="create",
            after_state=EventSerializer(event).data,
        )


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
