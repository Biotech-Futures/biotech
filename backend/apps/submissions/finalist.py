"""Rules for the finalist round: who is a finalist, when slides are due, and
the times its students can present. The due date is shown, not enforced:
the round stays open for now."""
from __future__ import annotations

from datetime import datetime, time

from django.apps import apps
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
    from apps.grading.services.finalist_notify import SYMPOSIUM_TZ

    day = apps.get_model("grading", "FinalistEmailSettings").load().slides_due
    if day is None:
        return None
    return datetime.combine(day, time(23, 59), tzinfo=SYMPOSIUM_TZ)


# --- the times, set on Management > Finalist Presentation ------------------------


def presentation_times():
    """This year's presentation times, earliest first."""
    PresentationSlot = apps.get_model("grading", "PresentationSlot")
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
    return apps.get_model("grading", "FinalistEmailSettings").load().symposium_date


def is_team_student(user, group_id: int) -> bool:
    """Only the team's students give their availability, each their own."""
    from apps.groups.models import GroupMembership

    return GroupMembership.objects.filter(
        group_id=group_id,
        user=user,
        left_at__isnull=True,
        membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
    ).exists()


def own_time_ids(user, group_id: int) -> list[int]:
    """The times this person said they can make, of this year's."""
    PresentationAvailability = apps.get_model("grading", "PresentationAvailability")
    answer = PresentationAvailability.objects.filter(group_id=group_id, user=user).first()
    if answer is None:
        return []
    return sorted(answer.slots.filter(year=current_cohort()).values_list("id", flat=True))


def save_own_times(user, group, slot_ids: list[int]) -> None:
    PresentationAvailability = apps.get_model("grading", "PresentationAvailability")
    answer, _ = PresentationAvailability.objects.get_or_create(group=group, user=user)
    answer.slots.set(slot_ids)
    # Records when they answered, even when only the ticks changed.
    answer.save(update_fields=["updated_at"])


def team_has_availability(group_id: int) -> bool:
    """At least one of the team's students has ticked a time this year."""
    PresentationAvailability = apps.get_model("grading", "PresentationAvailability")
    return PresentationAvailability.objects.filter(
        group_id=group_id, slots__year=current_cohort()
    ).exists()


def record_submitted_slides(entry: FinalistEntry) -> None:
    """The submitted slides, for the Finalist Presentation tab's table."""
    FinalistSlides = apps.get_model("grading", "FinalistSlides")
    FinalistSlides.objects.update_or_create(
        group=entry.group,
        defaults={
            "file": entry.submitted_presentation,
            "submitted_by": entry.submitted_by,
            "submitted_at": entry.submitted_at,
        },
    )


class FinalistEntrySerializer(serializers.ModelSerializer):
    """The team's entry; ``available_session_ids`` (and the submitted copy's)
    are the viewer's own times, since each student answers for themselves."""

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

    def _own(self, obj) -> list[int]:
        user = self.context.get("user")
        return own_time_ids(user, obj.group_id) if user is not None else []

    def get_available_session_ids(self, obj) -> list[int]:
        return self._own(obj)

    def get_submitted_session_ids(self, obj) -> list[int]:
        # Answers aren't frozen at submit: each student's stays their own.
        return self._own(obj)

    def get_submitted_by_name(self, obj) -> str:
        user = obj.submitted_by
        if user is None:
            return ""
        return f"{user.first_name} {user.last_name}".strip() or user.email


class FinalistAvailabilitySerializer(serializers.Serializer):
    session_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)

    def validate_session_ids(self, value):
        offered = set(presentation_times().values_list("id", flat=True))
        if set(value) - offered:
            raise serializers.ValidationError("One or more sessions are no longer available.")
        return sorted(set(value))
