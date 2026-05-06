from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, generics, mixins, permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.resources.models import RoleAssignmentHistory
from apps.users.models import User

from .filters import EventFilter
from .models import EventRsvp, Events
from .serializers import EventRsvpRequestSerializer, EventRsvpSerializer, EventRsvpUpsertSerializer, EventSerializer
from .services import get_user_registered_event_ids, register_user_for_event


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            return bool(request.user and request.user.is_staff)
        return True


class EventPagination(PageNumberPagination):
    """Single pagination class for every events-app list endpoint.

    Exposes ``page_size`` as a query param (capped at 100) so the FE
    Events page can request larger pages — the spec example calls out
    ``?page_size=100`` and the global ``DEFAULT_PAGINATION_CLASS`` does
    not honour ``page_size`` without an explicit override.

    Used by ``EventViewSet`` and the two invite list views; one class
    rather than three to prevent drift (e.g. one capping at 100, the
    other not) for no functional gain.
    """

    page_size = 20
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class EventViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = Events.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = EventPagination

    # Filtering / search wiring. ``DjangoFilterBackend`` consumes the
    # ``EventFilter`` (handles ``registered``/``mine``/``category``);
    # ``SearchFilter`` powers ``?search=...`` over event_name/description.
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EventFilter
    search_fields = ["event_name", "description"]
    ordering_fields = ["start_datetime", "ends_datetime"]
    ordering = ["start_datetime"]

    def get_queryset(self):
        # Active, non-past events. Ordering applied via the
        # ``OrderingFilter`` defaults so ``?ordering=...`` works.
        now = timezone.now()
        return Events.objects.filter(
            deleted_at__isnull=True,
            ends_datetime__gte=now,
        )

    def get_serializer_context(self):
        # Materialise the requesting user's GOING-RSVP'd event ids ONCE
        # per request so the ``registered`` SerializerMethodField stays
        # O(1) per row. Anonymous callers get an empty set → all rows
        # serialize ``"registered": false``. The key name mirrors the
        # serializer's vocabulary (``user_rsvp_event_ids``) so a future
        # reader doesn't conflate the *projected* ``registered`` field
        # with the *raw* RSVP record.
        context = super().get_serializer_context()
        context["user_rsvp_event_ids"] = get_user_registered_event_ids(self.request.user)
        return context

    def perform_create(self, serializer):
        event = serializer.save(host_user=self.request.user if self.request.user.is_authenticated else None)
        log_audit_event(
            actor=self.request.user if self.request.user.is_authenticated else None,
            entity_type="event",
            entity_id=event.id,
            action="create",
            after_state=EventSerializer(event).data,
        )


class EventSelfRegisterView(APIView):
    """``POST /events/v1/{id}/register/`` — authenticated self-registration.

    Deliberately separate from ``EventViewSet`` and from the
    admin/mentor-only ``EventInviteCreateView``: any authenticated
    user can self-register, while invite creation remains gated to
    non-students. Splitting the views keeps the permission classes
    co-located with the behaviour they protect.

    Idempotent. ``register_user_for_event`` uses ``update_or_create``
    so a second call (or a call after a previous DECLINED RSVP)
    leaves the row in ``GOING`` rather than the prior status.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: None,  # registered (created OR already going)
            400: None,  # event already ended
            404: None,  # event missing / soft-deleted
        },
    )
    def post(self, request, *args, **kwargs):
        # Service layer handles existence / past-event / dedupe rules;
        # the view only translates outcomes into HTTP responses (SRP,
        # "no fat views"). The 4xx responses are produced by DRF's
        # exception handler from the ``NotFound`` / ``ValidationError``
        # raised by the service — we don't catch them here on purpose
        # so error envelope shaping stays in one place.
        event_id = kwargs.get("id")
        event, rsvp, created = register_user_for_event(request.user, event_id)
        log_audit_event(
            actor=request.user,
            entity_type="event_rsvp",
            entity_id=rsvp.id,
            action="register" if created else "register_noop",
            after_state=EventRsvpSerializer(rsvp).data,
        )
        return Response(
            {
                "event_id": event.id,
                "user_id": request.user.id,
                "registered": True,
                "registered_at": rsvp.responded_at,
            },
            status=status.HTTP_200_OK,
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


class EventInviteListHTMLView(generics.ListAPIView):
    serializer_class = EventRsvpSerializer
    permission_classes = [IsNotStudent]
    pagination_class = EventPagination

    def get_queryset(self):
        event = get_object_or_404(Events, pk=self.kwargs.get("id"))
        return EventRsvp.objects.select_related("event", "user").filter(event=event).order_by("id")


class EventInviteListMeHTMLView(generics.ListAPIView):
    serializer_class = EventRsvpSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = EventPagination

    def get_queryset(self):
        return EventRsvp.objects.select_related("event", "user").filter(user=self.request.user).order_by("id")
