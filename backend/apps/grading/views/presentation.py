"""The Finalist Presentation tab: the times finalists can present at the
Symposium. They change year to year, so each year has its own; the date is
the Symposium date set on Notify Finalists."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.submissions.services import current_cohort

from ..models import FinalistEmailSettings, PresentationAvailability, PresentationSlot
from ..permissions import IsGrader
from ..services.results_notify import _person_name, natural_key


class PresentationSlotSerializer(serializers.ModelSerializer):
    starts_at = serializers.TimeField(format="%H:%M")
    ends_at = serializers.TimeField(format="%H:%M")

    class Meta:
        model = PresentationSlot
        fields = ["id", "starts_at", "ends_at"]

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "The end time must be after the start time."})
        year = self.instance.year if self.instance else self.context["year"]
        same = PresentationSlot.objects.filter(year=year, starts_at=starts_at, ends_at=ends_at)
        if self.instance is not None:
            same = same.exclude(pk=self.instance.pk)
        if same.exists():
            raise serializers.ValidationError({"starts_at": "That time is already listed."})
        return attrs


def _payload() -> dict:
    year = current_cohort()
    return {
        "year": year,
        # The day they're on; None until it's set on Notify Finalists.
        "symposium_date": FinalistEmailSettings.load().symposium_date,
        "slots": PresentationSlotSerializer(PresentationSlot.objects.filter(year=year), many=True).data,
    }


class PresentationSlotListView(APIView):
    """GET/POST /api/v1/grading/finalists/presentation-slots/ — this year's
    times, earliest first, and adding one (``starts_at``, ``ends_at`` as
    "HH:MM"). Both answer with the whole list."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request):
        return Response(_payload())

    def post(self, request):
        year = current_cohort()
        serializer = PresentationSlotSerializer(data=request.data, context={"year": year})
        serializer.is_valid(raise_exception=True)
        serializer.save(year=year)
        return Response(_payload(), status=status.HTTP_201_CREATED)


class PresentationSlotDetailView(APIView):
    """PATCH/DELETE /api/v1/grading/finalists/presentation-slots/<id>/ —
    change or remove one of this year's times. Both answer with the whole
    list."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    @staticmethod
    def _slot(slot_id: int) -> PresentationSlot:
        return get_object_or_404(PresentationSlot, pk=slot_id, year=current_cohort())

    def patch(self, request, slot_id: int):
        serializer = PresentationSlotSerializer(self._slot(slot_id), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(_payload())

    def delete(self, request, slot_id: int):
        self._slot(slot_id).delete()
        return Response(_payload())


class PresentationResponsesView(APIView):
    """GET /api/v1/grading/finalists/presentation-responses/ — this year's
    finalist teams, each student in them, and the times each said they can
    make. ``responded`` is false until a student answers.

    Shape:
        {"teams": [{"group_id", "group_name",
                    "students": [{"user_id", "name", "responded",
                                  "slot_ids": [...], "updated_at"}]}]}
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request):
        teams = sorted(
            Groups.objects.filter(
                deleted_at__isnull=True, year=current_cohort(), finalist_flag__isnull=False
            ),
            key=lambda team: natural_key(team.group_name),
        )
        memberships = (
            GroupMembership.objects.filter(
                group__in=teams,
                left_at__isnull=True,
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
                user__is_active=True,
            )
            .select_related("user")
        )
        students: dict[int, list] = {}
        for membership in memberships:
            students.setdefault(membership.group_id, []).append(membership.user)
        answers = {
            (answer.group_id, answer.user_id): answer
            for answer in PresentationAvailability.objects.filter(group__in=teams).prefetch_related("slots")
        }

        def student_row(team, user) -> dict:
            answer = answers.get((team.id, user.id))
            return {
                "user_id": user.id,
                "name": _person_name(user),
                "responded": answer is not None,
                "slot_ids": sorted(slot.id for slot in answer.slots.all()) if answer else [],
                "updated_at": answer.updated_at if answer else None,
            }

        return Response({
            "teams": [
                {
                    "group_id": team.id,
                    "group_name": team.group_name,
                    "students": [
                        student_row(team, user)
                        for user in sorted(students.get(team.id, []), key=lambda u: _person_name(u).lower())
                    ],
                }
                for team in teams
            ],
        })
