from django.utils import timezone
from rest_framework import serializers

from apps.groups.models import Groups

from .models import MeetingNote, MeetingSummary
from .permissions import can_manage_meeting


class MeetingNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingNote
        fields = ["body", "revision", "updated_by", "updated_at"]
        read_only_fields = ["revision", "updated_by", "updated_at"]


class MeetingNoteWriteSerializer(serializers.Serializer):
    # trim_whitespace off: the note is a document, trailing newlines matter.
    body = serializers.CharField(
        allow_blank=True, trim_whitespace=False, max_length=100_000
    )
    # Omit for last-writer-wins; send the revision you read to get a 409
    # on conflict instead.
    revision = serializers.IntegerField(required=False, min_value=0)


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


class GroupMeetingCreateSerializer(serializers.Serializer):
    group = serializers.PrimaryKeyRelatedField(
        queryset=Groups.objects.filter(deleted_at__isnull=True)
    )
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    agenda = serializers.CharField(required=False, allow_blank=True, default="")
    start_datetime = serializers.DateTimeField()
    ends_datetime = serializers.DateTimeField()
    timezone_name = serializers.CharField(required=False, default="UTC", max_length=50)
    join_link = serializers.URLField(max_length=255)

    def validate(self, attrs):
        start, end = attrs["start_datetime"], attrs["ends_datetime"]
        # Mirrors check_event_end_after_start so a bad payload is a 400,
        # not an IntegrityError surfacing as a 500.
        if end <= start:
            raise serializers.ValidationError(
                {"ends_datetime": "Must be after start_datetime."}
            )
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

    def validate(self, attrs):
        start = attrs.get("start_datetime")
        end = attrs.get("ends_datetime")
        # Half a reschedule can invert the interval and trip the DB CHECK.
        if (start is None) != (end is None):
            raise serializers.ValidationError(
                "start_datetime and ends_datetime must be sent together."
            )
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"ends_datetime": "Must be after start_datetime."}
            )
        return attrs
