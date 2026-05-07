from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, generics, mixins, permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.resources.models import RoleAssignmentHistory
from apps.users.models import User
from apps.users.utils.admin_scope import (
    can_admin_track,
    get_admin_track_ids,
    is_operational_admin,
)

from .filters import EventFilter
from .models import EventRsvp, Events
from .serializers import (
    EventRsvpRequestSerializer,
    EventRsvpSerializer,
    EventRsvpSubmitSerializer,
    EventRsvpUpsertSerializer,
    EventSerializer,
)
from .services import (
    get_user_registered_event_ids,
    register_user_for_event,
    set_user_rsvp,
    visible_events_queryset,
)


class EventManagePermission(permissions.BasePermission):
    """Permission rules for the public Events viewset.

    * **Read** (GET / HEAD / OPTIONS) — open: the queryset itself
      scopes results per-user via :func:`visible_events_queryset`,
      so leaving the permission permissive here means anonymous
      visitors and non-admin members both go through the same
      data-access layer. Defense-in-depth on the read path lives at
      the queryset, not the permission.
    * **Write** (POST / PUT / PATCH / DELETE) — operational admins
      only (``is_staff`` / ``is_superuser`` / ``AdminScope`` rows).
      Track-scope enforcement (a Track Admin may only push to their
      assigned tracks) lives in
      :meth:`EventViewSet.perform_create` because it requires
      inspecting the request body, which a permission class doesn't
      cleanly receive.

    Replaces the older ``IsAdminOrReadOnly`` which checked
    ``is_staff`` only and therefore locked Track Admins out of event
    creation — a divergence from the role spec that the new gate
    closes.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_operational_admin(request.user)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not is_operational_admin(request.user):
            return False
        # Track-scoped admins may only mutate events whose track FK
        # is in their scope. Global admins (``can_admin_track`` returns
        # True for any track) pass unconditionally.
        return can_admin_track(request.user, obj.track_id)


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
    permission_classes = [EventManagePermission]
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
        # Two-stage scoping:
        #
        #   1. Universal filter: active, non-past events. Same as
        #      before — DRF's ``OrderingFilter`` then applies the
        #      ``ordering`` default / ``?ordering=...`` override on top.
        #   2. Per-user visibility: ``visible_events_queryset`` mirrors
        #      the role-model gate (admin → admin scope, member →
        #      invited ∪ untargeted ∪ targeted-match, anonymous →
        #      untargeted only). Implemented in the service layer so
        #      the read-side and write-side rules stay in lockstep
        #      (a user who can SEE an event in the list is the same
        #      user who can RSVP to it via ``can_user_rsvp_to_event``,
        #      and vice-versa).
        now = timezone.now()
        base_qs = Events.objects.filter(
            deleted_at__isnull=True,
            ends_datetime__gte=now,
        )
        return visible_events_queryset(self.request.user, base_qs)

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
        # Track-scope enforcement on POST.
        #
        # ``EventManagePermission.has_permission`` already gated this
        # to operational admins; here we check the *body* — Track
        # Admins (``get_admin_track_ids`` returns a finite set) may
        # only create events whose ``track`` FK falls within their
        # scope, and may NOT create untargeted (platform-wide) events
        # because untargeted events are visible to everyone — that
        # would be a privilege escalation past their assigned tracks.
        #
        # Global admins (``get_admin_track_ids`` returns ``None``)
        # bypass this entirely and may target any track or none.
        track = serializer.validated_data.get("track")
        track_id = getattr(track, "id", None)
        admin_track_ids = get_admin_track_ids(self.request.user)
        if admin_track_ids is not None:
            if track_id is None:
                raise PermissionDenied(
                    "Untargeted events may only be created by global "
                    "administrators. Track admins must specify a track "
                    "within their assigned scope."
                )
            if track_id not in admin_track_ids:
                raise PermissionDenied(
                    "You may only create events for tracks within "
                    "your administrator scope."
                )

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

    A thin shortcut that flips the requesting user's RSVP to ``GOING``.
    The permission contract is enforced by the underlying service:

      * Authenticated user (``[IsAuthenticated]``)
      * AND a *legitimate target* of the event per
        :func:`apps.events.services.can_user_rsvp_to_event` — admin,
        explicit invitee, member of a targeted group/track, holder of
        a targeted role, or any user if the event is untargeted.

    Users who fail the gate get **403 Forbidden** rather than a silent
    success, so a student can't self-add to an event that wasn't
    pushed to their track / group by an admin.

    Idempotent. ``register_user_for_event`` (now a thin alias for
    ``set_user_rsvp(..., GOING)``) uses ``update_or_create`` so a
    second call (or a call after a previous DECLINED RSVP) leaves
    the row in ``GOING``.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: None,  # registered (created OR already going)
            400: None,  # event already ended
            403: None,  # user is not a legitimate target of the event
            404: None,  # event missing / soft-deleted
        },
    )
    def post(self, request, *args, **kwargs):
        # Service layer handles existence / past-event / visibility /
        # dedupe rules; the view only translates outcomes into HTTP
        # responses (SRP, "no fat views"). The 4xx responses are
        # produced by DRF's exception handler from the
        # ``NotFound`` / ``ValidationError`` / ``PermissionDenied``
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


class EventRsvpSetView(APIView):
    """``POST /events/v1/{id}/rsvp/`` — full user-side RSVP control.

    The general form of :class:`EventSelfRegisterView`: the user
    submits ``{"rsvp_status": "going" | "maybe" | "declined"}`` and
    the row is upserted to that status. Same gate, same idempotency,
    same response shape contract — just with the RSVP status free
    to vary.

    Why split from ``/register/`` rather than replace it? The FE's
    existing "Register" button calls ``/register/`` and only ever
    expects a ``registered: true`` response; keeping ``/register/``
    as a stable shortcut means the FE doesn't churn while we add the
    Maybe / Decline buttons. Both endpoints share
    :func:`apps.events.services.set_user_rsvp` so the gate cannot be
    bypassed by hitting one endpoint vs the other.

    ``PENDING`` is *not* an accepted status — that's the state an
    admin's invite leaves a row in until the user responds, and a
    user submitting ``pending`` would silently overwrite an admin's
    invite. Rejected at the serializer layer with a clean 400.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=EventRsvpSubmitSerializer,
        responses={
            200: None,  # RSVP set (created OR updated)
            400: None,  # bad rsvp_status, or event already ended
            403: None,  # user is not a legitimate target of the event
            404: None,  # event missing / soft-deleted
        },
    )
    def post(self, request, *args, **kwargs):
        submit = EventRsvpSubmitSerializer(data=request.data)
        submit.is_valid(raise_exception=True)
        rsvp_status_value = submit.validated_data["rsvp_status"]

        event, rsvp, created = set_user_rsvp(
            request.user,
            kwargs.get("id"),
            rsvp_status_value,
        )
        log_audit_event(
            actor=request.user,
            entity_type="event_rsvp",
            entity_id=rsvp.id,
            action="rsvp_create" if created else "rsvp_update",
            after_state=EventRsvpSerializer(rsvp).data,
        )
        return Response(
            {
                "event_id": event.id,
                "user_id": request.user.id,
                "rsvp_status": rsvp.rsvp_status,
                # Convenience boolean so the FE register button can
                # share a single response parser with ``/register/``.
                "registered": rsvp.rsvp_status == EventRsvp.RsvpStatus.GOING,
                "responded_at": rsvp.responded_at,
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
