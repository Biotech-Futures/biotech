import hmac
import re
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, generics, permissions, status, throttling, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.common.rbac import get_active_role_name
from apps.common.role_names import (
    ROLE_MENTOR,
    ROLE_SUPERVISOR,
    ROLE_ADMIN,
)
from apps.users.models import User
from apps.common.rbac import is_admin

from .filters import EventFilter
from .models import EventRsvp, EventTargetGroup, Events
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
    send_due_rsvp_reminders,
    set_user_rsvp,
    visible_events_queryset,
)


def _get_event_for_user_or_404(user, event_pk):
    """Resolve an event through ``visible_events_queryset`` or raise 404.

    Routes lookups through the same scoping logic the viewset uses so a
    Track-A caller hitting a Track-B event id gets a 404 instead of
    seeing roster data they shouldn't.
    """
    event_qs = visible_events_queryset(
        user, Events.objects.filter(deleted_at__isnull=True)
    )
    return get_object_or_404(event_qs, pk=event_pk)


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
        return is_admin(request.user)


class EventCursorPagination(CursorPagination):
    """Cursor pagination — skips COUNT(*) over visible_events_queryset."""

    # ``-id`` is the unique tiebreaker; without it cursors are ambiguous.
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = ("start_datetime", "-id")


class EventCursorPaginationDesc(EventCursorPagination):
    """``?when=past`` variant — newest first."""

    ordering = ("-start_datetime", "-id")


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
    pagination_class = EventCursorPagination
    lookup_field = "pk"

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EventFilter
    search_fields = ["event_name", "description"]
    ordering_fields = ["start_datetime", "ends_datetime"]
    ordering = ["start_datetime"]

    _WHEN_VALUES = {"upcoming", "past", "all"}

    def get_queryset(self):
        action = getattr(self, "action", None)
        # Restore and admin recovery lists are the only paths that opt into deleted events.
        include_deleted = (
            action == "restore"
            or (
                is_admin(self.request.user)
                and (
                    (self.request.query_params.get("include_deleted") or "").lower().strip() == "true"
                    or (self.request.query_params.get("deleted") or "").lower().strip() == "true"
                )
            )
        )
        base_qs = Events.objects.all() if include_deleted else Events.objects.filter(deleted_at__isnull=True)
        # ?when= only narrows the list; detail/update/destroy keep past
        # events visible so admins can still edit a finished one.
        if action == "list":
            if (self.request.query_params.get("deleted") or "").lower().strip() == "true":
                base_qs = base_qs.filter(deleted_at__isnull=False)
            when = (self.request.query_params.get("when") or "upcoming").lower()
            if when not in self._WHEN_VALUES:
                when = "upcoming"
            now = timezone.now()
            if when == "upcoming":
                base_qs = base_qs.filter(ends_datetime__gte=now)
            elif when == "past":
                base_qs = base_qs.filter(ends_datetime__lt=now)
                # Newest-first paging for the past view.
                self.pagination_class = EventCursorPaginationDesc

        qs = visible_events_queryset(self.request.user, base_qs).prefetch_related(
            "eventtargetgroup_set",
            "eventtargetrole_set",
        )
        # host_user is only read by audit-log serialization on writes;
        # skip the join on list to keep the row narrower.
        if action != "list":
            qs = qs.select_related("host_user")
        return qs.annotate(
            _accepted_count=Count("rsvps", filter=Q(rsvps__rsvp_status="accepted")),
            _waitlist_count=Count("rsvps", filter=Q(rsvps__rsvp_status="waitlisted")),
        )

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            # Scope accepted_event_ids to the current page only.
            request._page_event_ids = [e.id for e in page]
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def get_serializer_context(self):
        # `accepted_event_ids` powers the per-row `accepted` field.
        # `get_request_accepted_event_ids` memoizes on the request so
        # the filter and serializer share one query.
        context = super().get_serializer_context()
        context["accepted_event_ids"] = get_request_accepted_event_ids(self.request)
        return context

    def perform_create(self, serializer):
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

    @action(detail=True, methods=["post"], url_path="restore")
    @transaction.atomic
    def restore(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response(EventSerializer(instance, context=self.get_serializer_context()).data, status=status.HTTP_200_OK)

        # Target groups must be restored before their events can be restored.
        if EventTargetGroup.objects.filter(
            event=instance,
            group__deleted_at__isnull=False,
        ).exists():
            return Response(
                {"detail": "Cannot restore an event that targets a deleted group."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        before_state = EventSerializer(instance, context=self.get_serializer_context()).data
        instance.deleted_at = None
        instance.save(update_fields=["deleted_at"])
        instance.refresh_from_db()
        log_audit_event(
            actor=request.user,
            entity_type="event",
            entity_id=instance.id,
            action="restore",
            before_state=before_state,
            after_state=EventSerializer(instance, context=self.get_serializer_context()).data,
        )
        return Response(EventSerializer(instance, context=self.get_serializer_context()).data, status=status.HTTP_200_OK)


class EventRsvpSetView(APIView):
    """POST /api/v1/events/{id}/rsvp/ — set my RSVP to accepted/tentative/declined.

    Idempotent. PENDING is rejected — that's an admin-invite state, not a
    user choice. The legacy /events/v1/{id}/rsvp/ route still resolves.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        # Stable across every URL the canonical mount + legacy v1/ alias exposes
        # this view at (``/api/v1/events/<id>/rsvp/``, ``/events/<id>/rsvp/``,
        # and ``/events/v1/<id>/rsvp/``).
        # Without this, drf_spectacular auto-generates an id from the path,
        # collides with EventInviteCreateView (same path prefix + POST), and
        # disambiguates with ``_2`` / ``_3`` / ``_4`` suffixes that change
        # whenever the urlconf order shifts.
        operation_id="event_self_rsvp_set",
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


class IsNotStudent(permissions.BasePermission):
    # Role lookup is delegated to apps.common.rbac.get_active_role_name so
    # this permission stays in sync with every other RBAC consumer.

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if is_admin(request.user):
            return True

        role_name = get_active_role_name(request.user)
        if not role_name:
            return False
        return role_name in {ROLE_MENTOR, ROLE_SUPERVISOR, ROLE_ADMIN, "administrator"}


class EventInviteCreateView(APIView):
    permission_classes = [IsNotStudent]

    @extend_schema(
        # Stable id across all four mount points (see EventRsvpSetView for the
        # full rationale).
        operation_id="event_invite_create",
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
    pagination_class = EventInvitePagination

    def get_queryset(self):
        # Scope the event lookup through visible_events_queryset so a
        # mentor/supervisor can't pull the roster for an event outside
        # their track/scope. Returns 404 (not 403) on cross-track ids
        # to match the existing visibility semantics.
        event = _get_event_for_user_or_404(self.request.user, self.kwargs.get("id"))
        return EventRsvp.objects.select_related("event", "user").filter(event=event).order_by("id")


class EventInviteListMeHTMLView(generics.ListAPIView):
    serializer_class = EventRsvpSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = EventInvitePagination

    def get_queryset(self):
        qs = EventRsvp.objects.filter(user=self.request.user)
        # ``?event__in=1,2,3`` lets the FE pull just the rows it'll
        # display — avoids dragging the user's full RSVP history when
        # only the current event page needs status badges.
        raw = self.request.query_params.get("event__in")
        if raw:
            ids = [int(p) for p in raw.split(",") if p.strip().isdigit()]
            if ids:
                qs = qs.filter(event_id__in=ids)
        return qs.order_by("id")


class EventBulkInviteView(APIView):
    """POST /api/v1/events/{id}/rsvp/bulk/ — upsert many invites in one txn.

    Returns `created` / `updated` / `not_found` so the FE can show a
    partial-success summary instead of failing the whole call on one bad id.
    """

    permission_classes = [IsNotStudent]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "event_bulk_invite"

    @extend_schema(
        request=EventBulkInviteSerializer,
        responses={200: None},
    )
    def post(self, request, *args, **kwargs):
        event = get_object_or_404(Events, pk=kwargs.get("id"), deleted_at__isnull=True)

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


class RsvpReminderTriggerView(APIView):
    """Cron-trigger endpoint for the 24h RSVP reminder dispatcher.

    Called hourly by ``.github/workflows/rsvp-reminders.yml`` (no
    in-process scheduler / Celery worker). Auth is a shared secret
    header rather than a user session — there is no human caller. To
    keep the surface small:

    * ``RSVP_REMINDER_TOKEN`` must be set in the environment; if blank
      the endpoint returns 503 so a misconfigured deploy fails loud
      instead of silently exposing an unauthenticated trigger.
    * The header value is compared with ``hmac.compare_digest`` for
      constant-time matching.
    """

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        expected = getattr(settings, "RSVP_REMINDER_TOKEN", "") or ""
        if not expected:
            return Response(
                {"detail": "RSVP reminder trigger is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        provided = request.headers.get("X-Reminder-Token", "")
        if not hmac.compare_digest(provided, expected):
            return Response(
                {"detail": "Invalid token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        events_processed, sent, failed = send_due_rsvp_reminders()
        return Response(
            {
                "events_processed": events_processed,
                "emails_sent": sent,
                "emails_failed": failed,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# iCalendar (.ics) export
# ---------------------------------------------------------------------------


_ICS_DT_FMT = "%Y%m%dT%H%M%SZ"


def _ics_escape(value):
    """Escape per RFC 5545: backslash, comma, semicolon, and newlines.

    Returns an empty string for ``None`` so callers can drop the field
    by passing the model attribute directly.
    """
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace(",", "\\,")
    text = text.replace(";", "\\;")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "\\n")


def _ics_fold(line):
    """Fold long lines per RFC 5545 §3.1: max 75 octets per line.

    Continuation lines start with a single space. Done in bytes since
    multi-byte chars must not split mid-codepoint, but Django's iCal
    consumers are tolerant; we fold on UTF-8 byte boundaries.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts = []
    while len(encoded) > 75:
        # Walk back to avoid splitting a multi-byte codepoint.
        cut = 75
        while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(encoded[:cut].decode("utf-8"))
        encoded = encoded[cut:]
    parts.append(encoded.decode("utf-8"))
    return "\r\n ".join(parts)


def _filename_slug(text, fallback):
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", (text or "").strip()).strip("-")
    return (slug or fallback).lower()[:60]


class EventIcalExportView(APIView):
    """GET /events/v1/<id>/ical/ — download a one-event .ics file.

    Visibility scoped through ``visible_events_queryset`` so a caller
    only gets events they could already see in the regular list view.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="event_ical_export",
        responses={
            (200, "text/calendar"): bytes,
            404: None,
        },
    )
    def get(self, request, *args, **kwargs):
        event = _get_event_for_user_or_404(request.user, kwargs.get("id"))

        now_utc = timezone.now().astimezone(dt_timezone.utc)
        dtstamp = now_utc.strftime(_ICS_DT_FMT)
        dtstart = event.start_datetime.astimezone(dt_timezone.utc).strftime(_ICS_DT_FMT)
        dtend = event.ends_datetime.astimezone(dt_timezone.utc).strftime(_ICS_DT_FMT)

        # Stable UID per event id so re-downloads update the same
        # calendar entry instead of creating duplicates.
        uid = f"event-{event.id}@biotechfutures"

        # Hybrid keeps the physical address in LOCATION; URL field below
        # carries the join link separately.
        location = ""
        if event.event_format == Events.EventFormat.VIRTUAL:
            location = event.location_link or "Virtual event"
        elif event.location:
            location = event.location

        url_field = ""
        if event.location_link:
            url_field = event.location_link

        summary = _ics_escape(event.event_name or f"Event {event.id}")
        description = _ics_escape(event.description or "")
        location_escaped = _ics_escape(location)

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:-//{settings.BRAND_NAME}//Events//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{summary}",
        ]
        if description:
            lines.append(f"DESCRIPTION:{description}")
        if location_escaped:
            lines.append(f"LOCATION:{location_escaped}")
        if url_field:
            lines.append(f"URL:{url_field}")
        lines.extend(["END:VEVENT", "END:VCALENDAR"])

        body = "\r\n".join(_ics_fold(ln) for ln in lines) + "\r\n"
        filename = f"{_filename_slug(event.event_name, f'event-{event.id}')}.ics"

        response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
