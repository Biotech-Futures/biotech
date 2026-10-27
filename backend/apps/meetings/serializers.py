from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.groups.models import Groups

from .utils import detect_provider
from .models import MeetingNote, MeetingSummary
from .permissions import can_manage_meeting


class MeetingNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingNote
        fields = ["body", "revision", "updated_by", "updated_at"]
        read_only_fields = ["revision", "updated_by", "updated_at"]


class MeetingSummarySerializer(serializers.ModelSerializer):
    is_published = serializers.BooleanField(read_only=True)

    class Meta:
        model = MeetingSummary
        fields = ["body", "author", "published_at", "is_published", "updated_at"]
        read_only_fields = ["author", "published_at", "is_published", "updated_at"]


class MeetingSummaryWriteSerializer(serializers.Serializer):
    body = serializers.CharField(
        allow_blank=True, trim_whitespace=False, max_length=50_000
    )
    publish = serializers.BooleanField(required=False, allow_null=True, default=None)


class GroupMeetingSerializer(serializers.Serializer):
    """Read shape.

    Schedule fields are flattened off the linked event so the FE never has
    to know meetings are Events underneath. A plain Serializer rather than a
    ModelSerializer because almost every field is sourced across the
    OneToOne.
    """

    id = serializers.IntegerField(read_only=True)
    event_id = serializers.IntegerField(read_only=True)
    group = serializers.IntegerField(source="group_id", read_only=True)
    organiser = serializers.IntegerField(source="organiser_id", read_only=True)
    agenda = serializers.CharField(read_only=True)

    title = serializers.CharField(source="event.event_name", read_only=True)
    description = serializers.CharField(source="event.description", read_only=True)
    start_datetime = serializers.DateTimeField(
        source="event.start_datetime", read_only=True
    )
    ends_datetime = serializers.DateTimeField(
        source="event.ends_datetime", read_only=True
    )
    timezone_name = serializers.CharField(
        source="event.event_timezone", read_only=True
    )
    join_link = serializers.CharField(source="event.location_link", read_only=True)
    provider = serializers.SerializerMethodField()
    cancelled_at = serializers.DateTimeField(source="event.deleted_at", read_only=True)

    note = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def _user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_note(self, obj):
        # A reverse OneToOne raises a subclass of AttributeError when absent,
        # so getattr with a default is safe here.
        note = getattr(obj, "note", None)
        return MeetingNoteSerializer(note).data if note else None

    def get_summary(self, obj):
        """Drafts are visible to the mentor and admins only."""
        summary = getattr(obj, "summary", None)
        if summary is None:
            return None
        if summary.published_at is not None:
            return MeetingSummarySerializer(summary).data
        return (
            MeetingSummarySerializer(summary).data
            if can_manage_meeting(self._user(), obj)
            else None
        )

    def get_can_manage(self, obj):
        # Short-circuits on organiser_id for the common case; only falls
        # through to a membership query for co-mentors and admins.
        return can_manage_meeting(self._user(), obj)

    def get_provider(self, obj):
        return detect_provider(obj.join_link)


MAX_MEETING_MINUTES = 480


def _check_max_length(start, end):
    """Cap a meeting's length, whether the end came as ends_datetime or a duration."""
    if end - start > timedelta(minutes=MAX_MEETING_MINUTES):
        raise serializers.ValidationError(
            {"ends_datetime": f"A meeting can last at most {MAX_MEETING_MINUTES} minutes."}
        )


class GroupMeetingCreateSerializer(serializers.Serializer):
    group = serializers.PrimaryKeyRelatedField(
        queryset=Groups.objects.filter(deleted_at__isnull=True)
    )
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    agenda = serializers.CharField(required=False, allow_blank=True, default="")
    start_datetime = serializers.DateTimeField()
    ends_datetime = serializers.DateTimeField(required=False)
    duration_minutes = serializers.IntegerField(required=False,min_value=5,max_value=MAX_MEETING_MINUTES)
    timezone_name = serializers.CharField(required=False, default="UTC", max_length=50)
    join_link = serializers.URLField(max_length=255)

    def validate(self, attrs):
        duration = attrs.pop("duration_minutes", None)
        if "ends_datetime" not in attrs:
            if duration is None:
                raise serializers.ValidationError(
                    {"duration_minutes": "Must be provided if ends_datetime is not."}
                )
            attrs["ends_datetime"] = attrs["start_datetime"] + timedelta(minutes=duration)
        start, end = attrs["start_datetime"], attrs["ends_datetime"]
        # Mirrors check_event_end_after_start so a bad payload is a 400,
        # not an IntegrityError surfacing as a 500.
        if end <= start:
            raise serializers.ValidationError(
                {"ends_datetime": "Must be after start_datetime."}
            )
        _check_max_length(start, end)
        if start < timezone.now():
            raise serializers.ValidationError(
                {"start_datetime": "Cannot schedule a meeting in the past."}
            )
        return attrs


class GroupMeetingUpdateSerializer(serializers.Serializer):
    """Reschedule / edit.

    Group and organiser are immutable -- to move a meeting to another group,
    cancel it and schedule a new one.
    """

    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    agenda = serializers.CharField(required=False, allow_blank=True)
    start_datetime = serializers.DateTimeField(required=False)
    ends_datetime = serializers.DateTimeField(required=False)
    timezone_name = serializers.CharField(required=False, max_length=50)
    join_link = serializers.URLField(max_length=255, required=False)
    duration_minutes = serializers.IntegerField(required=False,min_value=5, max_value=MAX_MEETING_MINUTES)

    def validate(self, attrs):
        duration = attrs.pop("duration_minutes", None)
        start = attrs.get("start_datetime")

        # A reschedule may send a duration instead of an end time.
        if duration is not None:
            if start is None:
                raise serializers.ValidationError(
                    {"duration_minutes": "Send start_datetime with duration_minutes."}
                )
            if "ends_datetime" not in attrs:
                attrs["ends_datetime"] = start + timedelta(minutes=duration)

        end = attrs.get("ends_datetime")
        # Half a reschedule can invert the interval and trip the DB CHECK.
        if (start is None) != (end is None):
            raise serializers.ValidationError(
                "start_datetime and ends_datetime must be sent together."
            )
        if start and end:
            if end <= start:
                raise serializers.ValidationError(
                    {"ends_datetime": "Must be after start_datetime."}
                )
            _check_max_length(start, end)
        return attrs
