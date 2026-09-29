"""Rules for the finalist round: who is a finalist, and when it closes."""
from __future__ import annotations

from django.apps import apps
from rest_framework import serializers

from .models import FinalistDeadline, FinalistEntry, FinalistSession
from .services import DeadlineInfo


def is_finalist_group(group_id: int) -> bool:
    """A group is in the finalist round once it has been flagged and notified."""
    FinalistFlag = apps.get_model("grading", "FinalistFlag")
    return FinalistFlag.objects.filter(group_id=group_id, notified=True).exists()


def active_finalist_deadline() -> FinalistDeadline | None:
    return FinalistDeadline.objects.filter(is_active=True).order_by("-created_at").first()


def finalist_deadline_info() -> DeadlineInfo:
    """No extensions or grace period: the closing time is enforced as shown."""
    deadline = active_finalist_deadline()
    if deadline is None:
        return DeadlineInfo(closes_at=None, is_extended=False, enforced_until=None)
    return DeadlineInfo(
        closes_at=deadline.closes_at, is_extended=False, enforced_until=deadline.closes_at
    )


class FinalistSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinalistSession
        fields = ["id", "label"]
        read_only_fields = fields


class FinalistEntrySerializer(serializers.ModelSerializer):
    available_session_ids = serializers.SerializerMethodField()
    submitted_session_ids = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    stage = serializers.CharField(read_only=True)
    is_submitted = serializers.BooleanField(read_only=True)
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = FinalistEntry
        fields = [
            "available_session_ids",
            "presentation",
            "submitted_session_ids",
            "submitted_presentation",
            "submitted_at",
            "submitted_by_name",
            "reopened_at",
            "stage",
            "is_submitted",
            "is_locked",
            "updated_at",
        ]
        read_only_fields = fields

    def get_available_session_ids(self, obj) -> list[int]:
        # A retired session no longer counts as a choice the team can keep.
        return sorted(obj.available_sessions.filter(is_active=True).values_list("id", flat=True))

    def get_submitted_session_ids(self, obj) -> list[int]:
        return sorted(obj.submitted_sessions.values_list("id", flat=True))

    def get_submitted_by_name(self, obj) -> str:
        user = obj.submitted_by
        if user is None:
            return ""
        return f"{user.first_name} {user.last_name}".strip() or user.email


class FinalistAvailabilitySerializer(serializers.Serializer):
    session_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)

    def validate_session_ids(self, value):
        active = set(FinalistSession.active().values_list("id", flat=True))
        unknown = sorted(set(value) - active)
        if unknown:
            raise serializers.ValidationError("One or more sessions are no longer available.")
        return sorted(set(value))
