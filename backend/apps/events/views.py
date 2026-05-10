from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.users.models import User
from apps.users.utils.admin_scope import (
    get_admin_track_ids,
    is_operational_admin,
)

from .filters import EventFilter
from .models import EventRsvp, EventTargetGroup, EventTargetTrack, Events
from .serializers import (
    EventBulkInviteSerializer,
    EventRsvpRequestSerializer,
    EventRsvpSerializer,
    EventRsvpSubmitSerializer,
    EventRsvpUpsertSerializer,
    EventSerializer,
)
from .services import (
    get_request_accepted_event_ids,
    set_user_rsvp,
    visible_events_queryset,
)


class EventManagePermission(permissions.BasePermission):
    """Events are admin-pushed, not user-created.

    * Read    → open. Per-user scoping happens in `visible_events_queryset`.
    * Write   → operational admins only. Track-scope on POST is enforced
                in `EventViewSet.perform_create` because it needs the
                request body, not just the user.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_operational_admin(request.user)


class EventRsvpAdminPermission(permissions.BasePermission):
    message = "Admin access is required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and is_operational_admin(user))


def _event_scope_track_ids(event):
    track_ids = set()
    if getattr(event, "track_id", None) is not None:
        track_ids.add(event.track_id)
    track_ids.update(
        EventTargetTrack.objects.filter(event=event).values_list("track_id", flat=True)
    )
    track_ids.update(
        EventTargetGroup.objects.filter(event=event).values_list("group__track_id", flat=True)
    )
    return {track_id for track_id in track_ids if track_id is not None}


def _get_rsvp_admin_event_or_404(user, event_id):
    event = get_object_or_404(
        Events.objects.filter(deleted_at__isnull=True),
        pk=event_id,
    )

    admin_track_ids = get_admin_track_ids(user)
    if admin_track_ids is None:
        return event

    event_track_ids = _event_scope_track_ids(event)
    if not event_track_ids:
        raise PermissionDenied(
            "Untargeted events are global-admin only."
        )
    if not event_track_ids.issubset(set(admin_track_ids)):
        raise PermissionDenied(
            "You may only manage RSVP data for events within your admin scope."
        )
    return event


class EventPagination(PageNumberPagination):
    """Used by EventViewSet only. Honours `?page_size=` up to 100.

    The invite list views keep their own page_size=10 default.
    """

    page_size = 20
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class EventInvitePagination(PageNumberPagination):
    """Pagination for the invite/RSVP list endpoints.

    Kept separate from `EventPagination` to preserve the existing
    page_size=10 default on `/v1/{id}/rsvps` and `/v1/rsvps/me`.
    """

    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class EventViewSet(viewsets.ModelViewSet):
    queryset = Events.objects.all()
    serializer_class = EventSerializer
    permission_classes = [EventManagePermission]
    pagination_class = EventPagination
    lookup_field = "pk"

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EventFilter
    search_fields = ["event_name", "description"]
    ordering_fields = ["start_datetime", "ends_datetime"]
    ordering = ["start_datetime"]

    _WHEN_VALUES = {"upcoming", "past", "all"}

    def get_queryset(self):
        base_qs = Events.objects.filter(deleted_at__isnull=True)
        # ?when= only narrows the list view. Detail/update/destroy must
        # still see past events so admins can edit a finished one.
        if getattr(self, "action", None) == "list":
            when = (self.request.query_params.get("when") or "upcoming").lower()
            if when not in self._WHEN_VALUES:
                when = "upcoming"
            now = timezone.now()
            if when == "upcoming":
                base_qs = base_qs.filter(ends_datetime__gte=now)
            elif when == "past":
                base_qs = base_qs.filter(ends_datetime__lt=now)
        return visible_events_queryset(self.request.user, base_qs)

    def get_serializer_context(self):
        # `accepted_event_ids` powers the per-row `accepted` field.
        # `get_request_accepted_event_ids` memoizes on the request so
        # the filter and serializer share one query.
        context = super().get_serializer_context()
        context["accepted_event_ids"] = get_request_accepted_event_ids(self.request)
        return context

    def _enforce_track_scope(self, event_or_track_id, *, target_group_ids=None, target_track_ids=None):
        """Track admins can only touch events whose track + targets stay in scope.

        Untargeted (track=None) events remain global-admin only — they reach
        everyone, which would escalate past a track admin's scope.
        """
        admin_track_ids = get_admin_track_ids(self.request.user)
        if admin_track_ids is None:
            return

        track_id = (
            event_or_track_id.id if hasattr(event_or_track_id, "id") else event_or_track_id
        )
        if track_id is None:
            raise PermissionDenied(
                "Untargeted events are global-admin only; track admins "
                "must specify a track within their scope."
            )
        if track_id not in admin_track_ids:
            raise PermissionDenied(
                "You may only manage events for tracks within your scope."
            )
        if target_track_ids:
            for tid in target_track_ids:
                if tid not in admin_track_ids:
                    raise PermissionDenied("Target track is outside your admin scope.")
        if target_group_ids:
            from apps.groups.models import Groups

            out_of_scope = Groups.objects.filter(
                id__in=target_group_ids
            ).exclude(track_id__in=admin_track_ids).exists()
            if out_of_scope:
                raise PermissionDenied(
                    "Target group's parent track is outside your admin scope."
                )

    def perform_create(self, serializer):
        track = serializer.validated_data.get("track")
        groups = [g.id for g in serializer.validated_data.get("event_target_groups", []) or []]
        tracks = [t.id for t in serializer.validated_data.get("event_target_tracks", []) or []]
        self._enforce_track_scope(track, target_group_ids=groups, target_track_ids=tracks)

        event = serializer.save(
            host_user=self.request.user if self.request.user.is_authenticated else None
        )
        log_audit_event(
            actor=self.request.user if self.request.user.is_authenticated else None,
            entity_type="event",
            entity_id=event.id,
            action="create",
            after_state=EventSerializer(event).data,
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        before_state = EventSerializer(instance).data

        # Scope check runs against the *post-patch* state, so a track
        # admin can't move an event out of their scope mid-edit.
        new_track = serializer.validated_data.get("track", instance.track)
        groups = serializer.validated_data.get("event_target_groups")
        tracks = serializer.validated_data.get("event_target_tracks")
        group_ids = [g.id for g in groups] if groups is not None else None
        track_ids = [t.id for t in tracks] if tracks is not None else None
        self._enforce_track_scope(
            new_track, target_group_ids=group_ids, target_track_ids=track_ids
        )

        event = serializer.save()
        log_audit_event(
            actor=self.request.user,
            entity_type="event",
            entity_id=event.id,
            action="update",
            before_state=before_state,
            after_state=EventSerializer(event).data,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self._enforce_track_scope(instance.track)
        before_state = EventSerializer(instance).data
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])
        log_audit_event(
            actor=request.user,
            entity_type="event",
            entity_id=instance.id,
            action="delete",
            before_state=before_state,
            after_state=EventSerializer(instance).data,
        )
        return Response(EventSerializer(instance).data, status=status.HTTP_200_OK)


class EventRsvpSetView(APIView):
    """POST /events/v1/{id}/rsvp/ — set my RSVP to accepted/tentative/declined.

    Idempotent. PENDING is rejected — that's an admin-invite state, not a
    user choice.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=EventRsvpSubmitSerializer,
        responses={
            200: None,
            400: None,  # bad rsvp_status, or event already ended
            403: None,  # not a target
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
        # `rsvp_status` carries everything; FE derives the accepted
        # boolean as `rsvp_status === "accepted"`.
        return Response(
            {
                "event_id": event.id,
                "user_id": request.user.id,
                "rsvp_status": rsvp.rsvp_status,
                "responded_at": rsvp.responded_at,
            },
            status=status.HTTP_200_OK,
        )


class EventInviteCreateView(APIView):
    permission_classes = [EventRsvpAdminPermission]

    @extend_schema(
        request=EventRsvpRequestSerializer,
        responses={200: EventRsvpUpsertSerializer},
    )
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        event = _get_rsvp_admin_event_or_404(request.user, kwargs.get("id"))
        user = get_object_or_404(User, pk=kwargs.get("uid"))
        payload = EventRsvpRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        rsvp_status = payload.validated_data["rsvp_status"]
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
    permission_classes = [EventRsvpAdminPermission]
    pagination_class = EventInvitePagination

    def get_queryset(self):
        event = _get_rsvp_admin_event_or_404(self.request.user, self.kwargs.get("id"))
        return EventRsvp.objects.select_related("event", "user").filter(event=event).order_by("id")


class EventInviteListMeHTMLView(generics.ListAPIView):
    serializer_class = EventRsvpSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = EventInvitePagination

    def get_queryset(self):
        return EventRsvp.objects.select_related("event", "user").filter(
            user=self.request.user,
            event__deleted_at__isnull=True,
        ).order_by("id")


class EventBulkInviteView(APIView):
    """POST /events/v1/{id}/rsvp/bulk/ — upsert many invites in one txn.

    Returns `created` / `updated` / `not_found` so the FE can show a
    partial-success summary instead of failing the whole call on one bad id.
    """

    permission_classes = [EventRsvpAdminPermission]

    @extend_schema(
        request=EventBulkInviteSerializer,
        responses={200: None},
    )
    def post(self, request, *args, **kwargs):
        event = _get_rsvp_admin_event_or_404(request.user, kwargs.get("id"))

        payload = EventBulkInviteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        # De-dup but keep first-seen order so partial-success output is stable.
        user_ids = list(dict.fromkeys(payload.validated_data["user_ids"]))
        rsvp_status = payload.validated_data["rsvp_status"]
        responded_at = (
            timezone.now() if rsvp_status != EventRsvp.RsvpStatus.PENDING else None
        )

        existing_user_ids = set(
            User.objects.filter(id__in=user_ids).values_list("id", flat=True)
        )
        not_found = [uid for uid in user_ids if uid not in existing_user_ids]
        valid_user_ids = [uid for uid in user_ids if uid in existing_user_ids]

        created_ids = []
        updated_ids = []

        with transaction.atomic():
            existing_rsvps = {
                row.user_id: row
                for row in EventRsvp.objects.select_for_update().filter(
                    event=event, user_id__in=valid_user_ids
                )
            }
            for uid in valid_user_ids:
                row = existing_rsvps.get(uid)
                if row is None:
                    EventRsvp.objects.create(
                        event=event,
                        user_id=uid,
                        rsvp_status=rsvp_status,
                        responded_at=responded_at,
                    )
                    created_ids.append(uid)
                else:
                    row.rsvp_status = rsvp_status
                    row.responded_at = responded_at
                    row.save(update_fields=["rsvp_status", "responded_at"])
                    updated_ids.append(uid)

            log_audit_event(
                actor=request.user,
                entity_type="event_rsvp",
                entity_id=event.id,
                action="bulk_invite",
                after_state={
                    "event_id": event.id,
                    "rsvp_status": rsvp_status,
                    "created_user_ids": created_ids,
                    "updated_user_ids": updated_ids,
                },
            )

        return Response(
            {
                "event_id": event.id,
                "rsvp_status": rsvp_status,
                "created": created_ids,
                "updated": updated_ids,
                "not_found": not_found,
            },
            status=status.HTTP_200_OK,
        )
