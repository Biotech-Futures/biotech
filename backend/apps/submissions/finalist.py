"""Rules for the finalist round: who is a finalist, when slides are due, and
the times its students can present. The due date is shown, not enforced:
the round stays open for now."""
from __future__ import annotations

from datetime import datetime, time

from django.apps import apps
from django.utils import timezone
from rest_framework import serializers

from .models import FinalistEntry
from .services import current_cohort


def is_finalist_group(group_id: int) -> bool:
    """A group is in the finalist round once it has been flagged and notified."""
    FinalistFlag = apps.get_model("grading", "FinalistFlag")
    return FinalistFlag.objects.filter(group_id=group_id, notified=True).exists()


def slides_due_at() -> datetime | None:
    """When the slides are due: the end of the Slides Due day set on
    Management > Notify Finalists, Sydney time; None until it's set."""
    from apps.management.services.finalist_notify import SYMPOSIUM_TZ

    day = apps.get_model("management", "FinalistEmailSettings").load().slides_due
    if day is None:
        return None
    return datetime.combine(day, time(23, 59), tzinfo=SYMPOSIUM_TZ)


# --- the times, set on Management > Finalist Presentation ------------------------


def presentation_times():
    """This year's presentation times, earliest first."""
    PresentationSlot = apps.get_model("management", "PresentationSlot")
    return PresentationSlot.objects.filter(year=current_cohort())


def _clock(value) -> str:
    """24 hour, as the tab shows them: "9:30", "13:00"."""
    return f"{value.hour}:{value.minute:02d}"


def time_options() -> list[dict]:
    """The times as choices: ``{"id", "label"}`` with labels like "9:30 – 10:00"."""
    return [
        {"id": slot.id, "label": f"{_clock(slot.starts_at)} – {_clock(slot.ends_at)}"}
        for slot in presentation_times()
    ]


def symposium_date():
    """The day the times are on, set on Notify Finalists; None until it is."""
    return apps.get_model("management", "FinalistEmailSettings").load().symposium_date


def team_answer(group_id: int):
    """The team's availability, or None before anyone has given it."""
    PresentationAvailability = apps.get_model("management", "PresentationAvailability")
    return PresentationAvailability.objects.filter(group_id=group_id).select_related("submitted_by").first()


def team_time_ids(answer) -> list[int]:
    """The times the team can make, of this year's."""
    if answer is None:
        return []
    return sorted(answer.slots.filter(year=current_cohort()).values_list("id", flat=True))


def submit_team_times(user, group, slot_ids: list[int]) -> None:
    """The times the whole team can make, submitted by ``user``: anyone on
    the team, or an admin on its behalf."""
    PresentationAvailability = apps.get_model("management", "PresentationAvailability")
    answer, _ = PresentationAvailability.objects.get_or_create(group=group)
    answer.slots.set(slot_ids)
    answer.submitted_by = user
    answer.submitted_at = timezone.now()
    answer.save(update_fields=["submitted_by", "submitted_at", "updated_at"])


def team_has_availability(group_id: int) -> bool:
    """The team has submitted at least one of this year's times."""
    PresentationAvailability = apps.get_model("management", "PresentationAvailability")
    return PresentationAvailability.objects.filter(
        group_id=group_id, submitted_at__isnull=False, slots__year=current_cohort()
    ).exists()


def record_submitted_slides(entry: FinalistEntry) -> None:
    """The submitted slides, for the Finalist Presentation tab's table."""
    FinalistSlides = apps.get_model("management", "FinalistSlides")
    FinalistSlides.objects.update_or_create(
        group=entry.group,
        defaults={
            "file": entry.submitted_presentation,
            "submitted_by": entry.submitted_by,
            "submitted_at": entry.submitted_at,
        },
    )


class FinalistEntrySerializer(serializers.ModelSerializer):
    """The team's entry, with the team's availability: the times it can make
    and who submitted them, when."""

    available_session_ids = serializers.SerializerMethodField()
    availability_submitted_at = serializers.SerializerMethodField()
    availability_submitted_by_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    stage = serializers.CharField(read_only=True)
    is_submitted = serializers.BooleanField(read_only=True)
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = FinalistEntry
        fields = [
            "available_session_ids",
            "availability_submitted_at",
            "availability_submitted_by_name",
            "presentation",
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

    def _answer(self, obj):
        if "answer" not in self.context:
            self.context["answer"] = team_answer(obj.group_id)
        return self.context["answer"]

    def get_available_session_ids(self, obj) -> list[int]:
        return team_time_ids(self._answer(obj))

    def get_availability_submitted_at(self, obj):
        answer = self._answer(obj)
        return serializers.DateTimeField().to_representation(answer.submitted_at) if answer and answer.submitted_at else None

    def get_availability_submitted_by_name(self, obj) -> str:
        answer = self._answer(obj)
        return _name(answer.submitted_by) if answer and answer.submitted_at else ""

    def get_submitted_by_name(self, obj) -> str:
        return _name(obj.submitted_by)


def _name(user) -> str:
    if user is None:
        return ""
    return f"{user.first_name} {user.last_name}".strip() or user.email


class FinalistAvailabilitySerializer(serializers.Serializer):
    session_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        error_messages={"empty": "Choose at least one session your team can attend."},
    )

    def validate_session_ids(self, value):
        offered = set(presentation_times().values_list("id", flat=True))
        if set(value) - offered:
            raise serializers.ValidationError("One or more sessions are no longer available.")
        return sorted(set(value))
