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
    
class EventInviteSerializers(serializers.ModelSerializer):
    class Meta:
        model = EventInvite
        fields = ["id", "event", "user", "sent_datetime", "attendance_status", "rsvp_status"]

class EventInviteCreateSerializers(serializers.ModelSerializer):
    class Meta:
        model = EventInvite
        fields = ["event", "user", "sent_datetime"]
