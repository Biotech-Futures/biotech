from rest_framework import serializers
from .models import Events, EventInvite
from django.utils import timezone


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Events
        fields = [
            "id",
            "event_name",
            "description",
            "start_datetime",
            "ends_datetime",
            "location",
            "humanitix_link",
            "host_user",
            "event_image",
            "is_virtual",
        ]
        read_only_fields = ["id", "host_user"]

    def validate(self, attrs):
        start = attrs.get("start_datetime") or getattr(self.instance, "start_datetime", None)
        end = attrs.get("ends_datetime") or getattr(self.instance, "ends_datetime", None)
        is_virtual = attrs.get("is_virtual") if "is_virtual" in attrs else getattr(self.instance, "is_virtual", False)
        location = attrs.get("location") if "location" in attrs else getattr(self.instance, "location", None)

        # ---- Field-specific validation ----
        if start and end and end <= start:
            raise serializers.ValidationError({
                "ends_datetime": "End time must be after start time."
            })

        if is_virtual and location:
            raise serializers.ValidationError({
                "location": "Virtual events must not have a physical location."
            })

        return attrs

    def validate_start_datetime(self, value):
        """Prevent creating events in the past"""
        if value < timezone.now():
            raise serializers.ValidationError("Cannot create events in the past.")
        return value 
    
class EventInviteSerializer(serializers.Serializer):
    event_id = serializers.PrimaryKeyRelatedField(read_only=True, source="event")
    user_id = serializers.PrimaryKeyRelatedField(read_only=True, source="user")

    class Meta:
        model = EventInvite
        fields = [
            "id",
            "event_id",
            "user_id",
            "sent_datetime",
            "rsvp_status",
            "attendance_status",
        ]
        read_only_fields = [
            "id",
            "event_id",
            "user_id",
            "sent_datetime",
        ]

    def validate(self, attrs):
        """
        ensure attendance can only be True if RSVP is also True
        """
        rsvp = attrs.get("rsvp_status", getattr(self.instance, "rsvp_status", False))
        attendance = attrs.get("attendance_status", getattr(self.instance, "attendance_status", False))

        if attendance and not rsvp:
            raise serializers.ValidationError(
                {"attendance_status": "Cannot mark attendance unless RSVP is True."}
            )

        return attrs