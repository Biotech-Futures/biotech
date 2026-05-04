from django.utils import timezone
from rest_framework import serializers

from .models import EventRsvp, Events


class EventCurrentUserRsvpSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventRsvp
        fields = ["id", "rsvp_status", "responded_at"]


class EventSerializer(serializers.ModelSerializer):
    track_name = serializers.CharField(source="track.track_name", read_only=True, allow_null=True)
    host_name = serializers.SerializerMethodField()
    current_user_rsvp = serializers.SerializerMethodField()
    rsvp_summary = serializers.SerializerMethodField()

    class Meta:
        model = Events
        fields = [
            "id",
            "event_name",
            "description",
            "track",
            "track_name",
            "event_type",
            "start_datetime",
            "ends_datetime",
            "location",
            "link",
            "host_user",
            "host_name",
            "event_image",
            "is_virtual",
            "current_user_rsvp",
            "rsvp_summary",
        ]
        read_only_fields = ["id", "host_user"]

    def validate(self, attrs):
        start = attrs.get("start_datetime") or getattr(self.instance, "start_datetime", None)
        end = attrs.get("ends_datetime") or getattr(self.instance, "ends_datetime", None)
        is_virtual = attrs.get("is_virtual") if "is_virtual" in attrs else getattr(self.instance, "is_virtual", False)
        location = attrs.get("location") if "location" in attrs else getattr(self.instance, "location", None)

        if start and end and end <= start:
            raise serializers.ValidationError({"ends_datetime": "End time must be after start time."})

        if is_virtual and location:
            raise serializers.ValidationError({"location": "Virtual events must not have a physical location."})

        return attrs

    def validate_start_datetime(self, value):
        if self.instance is None and value < timezone.now():
            raise serializers.ValidationError("Cannot create events in the past.")
        return value

    def get_host_name(self, obj):
        if not obj.host_user_id or obj.host_user is None:
            return None
        return obj.host_user.get_full_name().strip() or obj.host_user.email

    def get_current_user_rsvp(self, obj):
        # The list/detail views prefetch the current user's RSVP so the SPA can render one
        # stable field instead of making a second per-event lookup.
        prefetched_rsvps = getattr(obj, "_current_user_rsvps", None)
        if prefetched_rsvps is None:
            return None
        if not prefetched_rsvps:
            return None
        return EventCurrentUserRsvpSerializer(prefetched_rsvps[0]).data

    def get_rsvp_summary(self, obj):
        return {
            "pending": int(getattr(obj, "pending_rsvp_count", 0) or 0),
            "going": int(getattr(obj, "going_rsvp_count", 0) or 0),
            "maybe": int(getattr(obj, "maybe_rsvp_count", 0) or 0),
            "declined": int(getattr(obj, "declined_rsvp_count", 0) or 0),
            "total": int(getattr(obj, "rsvp_total_count", 0) or 0),
        }


class EventRsvpSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventRsvp
        fields = ["id", "event", "user", "rsvp_status", "responded_at"]


class EventRsvpUpsertSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventRsvp
        fields = ["event", "user", "rsvp_status", "responded_at"]


class EventRsvpRequestSerializer(serializers.Serializer):
    rsvp_status = serializers.ChoiceField(
        choices=EventRsvp.RsvpStatus.choices,
        required=False,
        default=EventRsvp.RsvpStatus.GOING,
    )
