"""The Finalist Presentation tab: the times finalists can present at the
Symposium. They change year to year, so each year has its own; the date is
the Symposium date set on Notify Finalists."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import IsStaffOrAdmin
from apps.common.storage import serve_managed_file
from apps.grading.models import FinalistFlag
from apps.grading.services.text import natural_key
from apps.groups.models.groups import Groups
from apps.submissions.services import current_cohort
from apps.submissions.storage import FINALIST_SLIDES_FILES

from ..models import (
    FinalistEmailSettings,
    FinalistSlides,
    PresentationAllocation,
    PresentationAvailability,
    PresentationSettings,
    PresentationSlot,
)
from ..services.deadline import submissions_still_open
from ..services.send_guard import person_name


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
        # Whether finalists see them yet.
        "times_shown": PresentationSettings.load().times_shown,
        # While any team can still submit (extensions and grace hours
        # included), who the finalists are isn't settled: the times stay hidden.
        "submissions_open": submissions_still_open(),
    }


class PresentationSlotListView(APIView):
    """GET/POST /api/v1/management/finalists/presentation-slots/ — this year's
    times, earliest first, and adding one (``starts_at``, ``ends_at`` as
    "HH:MM"). Both answer with the whole list."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        return Response(_payload())

    def post(self, request):
        year = current_cohort()
        serializer = PresentationSlotSerializer(data=request.data, context={"year": year})
        serializer.is_valid(raise_exception=True)
        serializer.save(year=year)
        return Response(_payload(), status=status.HTTP_201_CREATED)


class PresentationSlotDetailView(APIView):
    """PATCH/DELETE /api/v1/management/finalists/presentation-slots/<id>/ —
    change or remove one of this year's times. Both answer with the whole
    list."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

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


TIMES_WAIT = (
    "Submissions are still open (including any extensions) - "
    "the time slots can be shown once the window has closed."
)


class PresentationTimesShownView(APIView):
    """PATCH /api/v1/management/finalists/presentation-times-shown/ —
    ``{"times_shown": true}`` shows finalists this year's times to give their
    availability; false hides them again. Answers with the whole list.
    Showing them is refused while submissions are still open (baseline
    window or any extension, grace hours included); hiding is always allowed."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def patch(self, request):
        shown = request.data.get("times_shown")
        if not isinstance(shown, bool):
            return Response({"detail": "times_shown must be true or false"}, status=status.HTTP_400_BAD_REQUEST)
        if shown and submissions_still_open():
            return Response({"detail": TIMES_WAIT}, status=status.HTTP_400_BAD_REQUEST)
        settings = PresentationSettings.load()
        settings.times_shown = shown
        settings.save()
        return Response(_payload())


# Where finalists' slides are kept, as the finalist step uploads them.
SLIDES_FILES = FINALIST_SLIDES_FILES


def _finalist_teams() -> list:
    """This year's finalist teams, by number."""
    return sorted(
        Groups.objects.filter(
            deleted_at__isnull=True, year=current_cohort(), finalist_flag__isnull=False
        ).select_related("finalist_flag__presentation_allocation"),
        key=lambda team: natural_key(team.group_name),
    )


def _allocated_slot_id(team) -> int | None:
    allocation = getattr(team.finalist_flag, "presentation_allocation", None)
    return allocation.slot_id if allocation else None


class PresentationResponsesView(APIView):
    """GET /api/v1/management/finalists/presentation-responses/ — this year's
    finalist teams, the times each team said it can make, and when it
    answered and who for it (``answered_at`` is null until it has).
    ``allocated_slot_id`` is the time the team has been given, if any.

    Shape:
        {"teams": [{"group_id", "group_name", "allocated_slot_id",
                    "slot_ids": [...], "answered_at", "answered_by"}]}
    """

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        teams = _finalist_teams()
        # Only submitted answers: times carried over from before, when each
        # student answered, count once the team has checked and submitted them.
        answers = {
            answer.group_id: answer
            for answer in PresentationAvailability.objects.filter(group__in=teams, submitted_at__isnull=False)
            .select_related("submitted_by")
            .prefetch_related("slots")
        }

        def row(team) -> dict:
            answer = answers.get(team.id)
            return {
                "group_id": team.id,
                "group_name": team.group_name,
                "allocated_slot_id": _allocated_slot_id(team),
                "slot_ids": sorted(slot.id for slot in answer.slots.all()) if answer else [],
                "answered_at": answer.submitted_at if answer else None,
                "answered_by": person_name(answer.submitted_by) if answer and answer.submitted_by else None,
            }

        return Response({"teams": [row(team) for team in teams]})


class PresentationSlidesView(APIView):
    """GET /api/v1/management/finalists/presentation-slides/ — this year's
    finalist teams and the slides each has handed in for its presentation,
    with the date they're due (set on Notify Finalists). The latest handed
    in come first; teams still to hand theirs in follow, by number.

    Shape:
        {"slides_due": "2026-10-16" | null,
         "teams": [{"group_id", "group_name", "submitted",
                    "file_name", "submitted_by", "submitted_at"}]}
    """

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        teams = _finalist_teams()
        slides = {
            deck.group_id: deck
            for deck in FinalistSlides.objects.filter(group__in=teams).select_related("submitted_by")
        }

        def row(team) -> dict:
            deck = slides.get(team.id)
            return {
                "group_id": team.id,
                "group_name": team.group_name,
                "submitted": deck is not None,
                "file_name": (deck.file or {}).get("name", "") if deck else "",
                "submitted_by": person_name(deck.submitted_by) if deck and deck.submitted_by else None,
                "submitted_at": deck.submitted_at if deck else None,
            }

        # Stable sort: the not-yet teams keep their number order at the end.
        in_first = sorted(
            teams,
            key=lambda team: (
                team.id not in slides,
                -slides[team.id].submitted_at.timestamp() if team.id in slides else 0,
            ),
        )
        return Response({
            "slides_due": FinalistEmailSettings.load().slides_due,
            "teams": [row(team) for team in in_first],
        })


class PresentationSlidesFileView(APIView):
    """GET /api/v1/management/finalists/presentation-slides/<group_id>/file/ —
    open a finalist team's slides: a PDF in the browser, anything else as a
    download (only a PDF is safe to show inline). 404 until they're in."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, group_id: int):
        team = next((t for t in _finalist_teams() if t.id == group_id), None)
        deck = FinalistSlides.objects.filter(group=team).first() if team else None
        stored = (deck.file or {}) if deck else {}
        if not stored.get("storage_key"):
            return Response({"detail": "No slides handed in yet."}, status=status.HTTP_404_NOT_FOUND)
        mime = stored.get("mime")
        return serve_managed_file(
            resolve_url=SLIDES_FILES.resolve_url,
            open_file=SLIDES_FILES.open,
            storage_key=stored["storage_key"],
            filename=stored.get("name") or "slides",
            mime_type=mime,
            size=stored.get("size"),
            as_attachment=mime != "application/pdf",
        )


class PresentationAllocationView(APIView):
    """PUT /api/v1/management/finalists/presentation-allocation/<group_id>/ —
    give a finalist team one of this year's times, ``{"slot_id": id}``, or
    take it away, ``{"slot_id": null}``. Several teams may share a time."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def put(self, request, group_id: int):
        flag = get_object_or_404(
            FinalistFlag,
            group_id=group_id,
            group__deleted_at__isnull=True,
            group__year=current_cohort(),
        )
        slot_id = request.data.get("slot_id")
        if slot_id is None:
            PresentationAllocation.objects.filter(flag=flag).delete()
            return Response({"group_id": group_id, "slot_id": None})
        # A number only: JSON's true would otherwise pass as 1.
        is_id = isinstance(slot_id, int) and not isinstance(slot_id, bool)
        slot = PresentationSlot.objects.filter(pk=slot_id if is_id else None, year=current_cohort()).first()
        if slot is None:
            return Response(
                {"detail": "That time isn't one of this year's."}, status=status.HTTP_400_BAD_REQUEST
            )
        PresentationAllocation.objects.update_or_create(flag=flag, defaults={"slot": slot})
        return Response({"group_id": group_id, "slot_id": slot.id})
