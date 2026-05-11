from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import (
    EventRsvp,
    EventTargetGroup,
    EventTargetRole,
    EventTargetTrack,
    Events,
)


class _LazyPKField(serializers.PrimaryKeyRelatedField):
    """PrimaryKeyRelatedField that resolves its queryset on first use.

    Overriding get_queryset short-circuits DRF's queryset assert and lets
    us reference Groups / Tracks / Roles without the events ↔ groups ↔
    resources import cycle at module load.
    """

    def __init__(self, model_path, **kwargs):
        self._model_path = model_path
        super().__init__(**kwargs)

    def get_queryset(self):
        from importlib import import_module

        module_path, attr = self._model_path.rsplit(".", 1)
        return getattr(import_module(module_path), attr).objects.all()


class EventSerializer(serializers.ModelSerializer):
    # `accepted` = "this user has RSVP'd ACCEPTED for this event."
    # The view materialises the set once via
    # services.get_request_accepted_event_ids so this stays an O(1)
    # lookup per row, no N+1.
    accepted = serializers.SerializerMethodField()
    # On PATCH: omit a target_*_ids field to leave it alone, pass [] to clear.
    target_group_ids = _LazyPKField(
        "apps.groups.models.Groups",
        many=True,
        required=False,
        source="event_target_groups",
        write_only=True,
    )
    target_track_ids = _LazyPKField(
        "apps.groups.models.Tracks",
        many=True,
        required=False,
        source="event_target_tracks",
        write_only=True,
    )
    target_role_ids = _LazyPKField(
        "apps.resources.models.Roles",
        many=True,
        required=False,
        source="event_target_roles",
        write_only=True,
    )
    target_groups = serializers.SerializerMethodField()
    target_tracks = serializers.SerializerMethodField()
    target_roles = serializers.SerializerMethodField()
    # event_image is a CharField on the model but should behave like the other
    # URL-bearing fields (location_link is URLField; dashboard exposes
    # event_image as URLField). Promoting it here keeps validation uniform —
    # rejects javascript: and other non-http(s) schemes, accepts blank/null.
    event_image = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=255,
    )

    class Meta:
        model = Events
        fields = [
            "id",
            "event_name",
            "description",
            "track",
            "event_type",
            "start_datetime",
            "ends_datetime",
            "location",
            "location_link",
            "host_user",
            "event_image",
            "is_virtual",
            "accepted",
            "target_groups",
            "target_tracks",
            "target_roles",
            "target_group_ids",
            "target_track_ids",
            "target_role_ids",
        ]
        read_only_fields = [
            "id",
            "host_user",
            "accepted",
            "target_groups",
            "target_tracks",
            "target_roles",
        ]

    def get_accepted(self, event):
        accepted_event_ids = self.context.get("accepted_event_ids") or set()
        return event.id in accepted_event_ids

    def get_target_groups(self, event):
        return list(
            EventTargetGroup.objects.filter(event=event).values_list("group_id", flat=True)
        )

    def get_target_tracks(self, event):
        return list(
            EventTargetTrack.objects.filter(event=event).values_list("track_id", flat=True)
        )

    def get_target_roles(self, event):
        return list(
            EventTargetRole.objects.filter(event=event).values_list("role_id", flat=True)
        )

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

    @transaction.atomic
    def create(self, validated_data):
        groups = validated_data.pop("event_target_groups", None)
        tracks = validated_data.pop("event_target_tracks", None)
        roles = validated_data.pop("event_target_roles", None)
        event = super().create(validated_data)
        self._apply_targets(event, groups, tracks, roles)
        return event

    @transaction.atomic
    def update(self, instance, validated_data):
        groups = validated_data.pop("event_target_groups", _UNSET)
        tracks = validated_data.pop("event_target_tracks", _UNSET)
        roles = validated_data.pop("event_target_roles", _UNSET)
        instance = super().update(instance, validated_data)
        self._apply_targets(
            instance,
            None if groups is _UNSET else groups,
            None if tracks is _UNSET else tracks,
            None if roles is _UNSET else roles,
        )
        return instance

    @staticmethod
    def _apply_targets(event, groups, tracks, roles):
        # None = field absent (no-op); [] = explicit clear.
        if groups is not None:
            EventTargetGroup.objects.filter(event=event).delete()
            EventTargetGroup.objects.bulk_create(
                [EventTargetGroup(event=event, group=g) for g in groups],
                ignore_conflicts=True,
            )
        if tracks is not None:
            EventTargetTrack.objects.filter(event=event).delete()
            EventTargetTrack.objects.bulk_create(
                [EventTargetTrack(event=event, track=t) for t in tracks],
                ignore_conflicts=True,
            )
        if roles is not None:
            EventTargetRole.objects.filter(event=event).delete()
            EventTargetRole.objects.bulk_create(
                [EventTargetRole(event=event, role=r) for r in roles],
                ignore_conflicts=True,
            )


_UNSET = object()


class EventRsvpSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventRsvp
        fields = ["id", "event", "user", "rsvp_status", "responded_at"]


class EventRsvpUpsertSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventRsvp
        fields = ["event", "user", "rsvp_status", "responded_at"]


class EventRsvpRequestSerializer(serializers.Serializer):
    """Admin-side invite payload — PENDING allowed, default."""

    rsvp_status = serializers.ChoiceField(
        choices=EventRsvp.RsvpStatus.choices,
        required=False,
        default=EventRsvp.RsvpStatus.PENDING,
    )


class EventRsvpSubmitSerializer(serializers.Serializer):
    """User-side RSVP payload for POST /events/v1/{id}/rsvp/.

    PENDING is excluded — that's an admin-invite state. Restricting
    choices here means a stray `rsvp_status=pending` body is rejected
    with a clean 400 instead of silently overwriting an admin invite.
    """

    USER_SUBMITTABLE_CHOICES = [
        (EventRsvp.RsvpStatus.ACCEPTED, "Accepted"),
        (EventRsvp.RsvpStatus.TENTATIVE, "Tentative"),
        (EventRsvp.RsvpStatus.DECLINED, "Declined"),
    ]

    rsvp_status = serializers.ChoiceField(choices=USER_SUBMITTABLE_CHOICES)


class EventBulkInviteSerializer(serializers.Serializer):
    """Up to 200 invites per call; PENDING is the invite-issued default."""

    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=200,
    )
    rsvp_status = serializers.ChoiceField(
        choices=EventRsvp.RsvpStatus.choices,
        required=False,
        default=EventRsvp.RsvpStatus.PENDING,
    )