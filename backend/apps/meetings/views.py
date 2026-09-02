from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.audit.services import log_audit_event
from apps.common.rbac import is_admin

from . import services
from .permissions import (
    IsGroupMentorOrReadOnly,
    IsGroupParticipant,
    can_manage_meeting,
    is_group_mentor,
)
from .serializers import (
    GroupMeetingCreateSerializer,
    GroupMeetingSerializer,
    GroupMeetingUpdateSerializer,
    MeetingNoteSerializer,
    MeetingNoteWriteSerializer,
    MeetingSummarySerializer,
    MeetingSummaryWriteSerializer,
)


class MeetingPagination(PageNumberPagination):
    page_size = 20
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class GroupMeetingViewSet(viewsets.ModelViewSet):
    """Mentor-scheduled group meetings.

    Query params on list: ``?group=<id>``, ``?when=upcoming|past``,
    ``?include_cancelled=true``.
    """

    serializer_class = GroupMeetingSerializer
    permission_classes = [permissions.IsAuthenticated, IsGroupMentorOrReadOnly]
    pagination_class = MeetingPagination
    lookup_field = "pk"

    def get_queryset(self):
        params = self.request.query_params
        include_cancelled = (
            params.get("include_cancelled") or ""
        ).lower().strip() == "true"

        qs = services.visible_meetings_queryset(
            self.request.user, include_cancelled=include_cancelled
        ).select_related("note", "summary")

        group_id = params.get("group")
        if group_id:
            qs = qs.filter(group_id=group_id)

        when = (params.get("when") or "").lower().strip()
        now = timezone.now()
        if when == "upcoming":
            qs = qs.filter(event__ends_datetime__gte=now).order_by(
                "event__start_datetime"
            )
        elif when == "past":
            qs = qs.filter(event__ends_datetime__lt=now).order_by(
                "-event__start_datetime"
            )
        return qs

    def create(self, request, *args, **kwargs):
        payload = GroupMeetingCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        group = data["group"]

        # Object-level permissions cannot run on create -- there is no object
        # yet -- so the mentor check happens here against the target group.
        if not (is_admin(request.user) or is_group_mentor(request.user, group.id)):
            raise PermissionDenied(
                "Only a mentor or supervisor of this group can schedule a meeting."
            )

        meeting = services.schedule_meeting(
            organiser=request.user,
            group=group,
            name=data["title"],
            description=data.get("description", ""),
            agenda=data.get("agenda", ""),
            start=data["start_datetime"],
            end=data["ends_datetime"],
            timezone_name=data.get("timezone_name") or "UTC",
            join_link=data["join_link"],
        )
        log_audit_event(
            actor=request.user,
            entity_type="group_meeting",
            entity_id=meeting.id,
            action="create",
            after_state={
                "group_id": group.id,
                "event_id": meeting.event_id,
                "start_datetime": data["start_datetime"].isoformat(),
            },
        )
        return Response(
            self.get_serializer(meeting).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        meeting = self.get_object()
        payload = GroupMeetingUpdateSerializer(
            data=request.data, partial=kwargs.get("partial", False)
        )
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        before = {
            "start_datetime": meeting.event.start_datetime.isoformat(),
            "event_name": meeting.event.event_name,
        }
        services.update_meeting(meeting, **data)
        meeting.refresh_from_db()

        log_audit_event(
            actor=request.user,
            entity_type="group_meeting",
            entity_id=meeting.id,
            action="update",
            before_state=before,
            after_state={
                "start_datetime": meeting.event.start_datetime.isoformat(),
                "event_name": meeting.event.event_name,
            },
        )
        return Response(self.get_serializer(meeting).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Cancel -- soft delete on the linked event, never a hard delete."""
        meeting = self.get_object()
        services.cancel_meeting(meeting)
        log_audit_event(
            actor=request.user,
            entity_type="group_meeting",
            entity_id=meeting.id,
            action="cancel",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["get", "patch"],
        url_path="note",
        permission_classes=[permissions.IsAuthenticated, IsGroupParticipant],
    )
    def note(self, request, pk=None):
        """Shared live note -- every participant may write."""
        meeting = self.get_object()

        if request.method == "GET":
            return Response(
                MeetingNoteSerializer(services.get_or_create_note(meeting)).data
            )

        payload = MeetingNoteWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            note = services.update_note(
                meeting,
                user=request.user,
                body=payload.validated_data["body"],
                revision=payload.validated_data.get("revision"),
            )
        except services.StaleRevision as exc:
            # 409 not 400: the request was well-formed, it just lost the
            # race. The FE should re-fetch and merge, not blindly re-submit.
            return Response(
                {"detail": str(exc), "current_revision": exc.current},
                status=status.HTTP_409_CONFLICT,
            )

        services.broadcast_note(meeting, note)
        return Response(MeetingNoteSerializer(note).data)

    @action(detail=True, methods=["get", "put"], url_path="summary")
    def summary(self, request, pk=None):
        """Mentor-controlled wrap-up.

        Read is participant-scoped by IsGroupMentorOrReadOnly; write lands on
        the mentor branch of that same permission.
        """
        meeting = self.get_object()

        if request.method == "GET":
            summary = getattr(meeting, "summary", None)
            hidden_draft = (
                summary is not None
                and summary.published_at is None
                and not can_manage_meeting(request.user, meeting)
            )
            if summary is None or hidden_draft:
                return Response(
                    {"detail": "No summary yet."}, status=status.HTTP_404_NOT_FOUND
                )
            return Response(MeetingSummarySerializer(summary).data)

        payload = MeetingSummaryWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        summary = services.upsert_summary(
            meeting,
            author=request.user,
            body=payload.validated_data["body"],
            publish=payload.validated_data.get("publish"),
        )
        log_audit_event(
            actor=request.user,
            entity_type="meeting_summary",
            entity_id=meeting.id,
            action="upsert",
            after_state={"published": summary.is_published},
        )
        return Response(MeetingSummarySerializer(summary).data)

    @action(detail=True, methods=["post"], url_path="sync-attendees")
    def sync_attendees(self, request, pk=None):
        """Backfill RSVPs after the group roster changes.

        A member who joined late still gets the meeting on their calendar
        and in the reminder run.
        """
        meeting = self.get_object()
        added = services.sync_attendees(meeting)
        return Response({"added": added})
