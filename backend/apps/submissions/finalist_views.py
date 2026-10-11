"""Finalist round endpoints: availability, presentation, submit and reopen."""
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import group_participant_qs, is_admin
from apps.common.storage import serve_managed_file
from apps.groups.models import Groups
from config.errors import GroupAccessDenied

from .errors import (
    AvailabilityRequired,
    FileNotUploadedYet,
    NoFileUploaded,
    NotAFinalist,
    NotSubmittedYet,
    PresentationRequired,
    SubmissionLocked,
    TimesNotShown,
)
from .finalist import (
    FinalistAvailabilitySerializer,
    FinalistEntrySerializer,
    is_finalist_group,
    record_submitted_slides,
    slides_due_at,
    submit_team_times,
    symposium_date,
    team_has_availability,
    time_options,
    times_shown,
)
from .models import FinalistEntry
from .storage import FINALIST_SLIDES_FILES, slides_file_name
from .uploads import FINALIST_MAX_UPLOAD_SIZE, validate_presentation_file

# The slides' own container, which the Finalist Presentation tab opens them from.
_storage = FINALIST_SLIDES_FILES


def _finalist_group(group_id: int) -> Groups:
    group = get_object_or_404(Groups, id=group_id, deleted_at__isnull=True)
    if not is_finalist_group(group.id):
        raise NotAFinalist()
    return group


def _require_can_view(user, group_id: int) -> None:
    if is_admin(user) or user.is_staff or user.is_superuser:
        return
    if not group_participant_qs(user, group_id).exists():
        raise GroupAccessDenied()


def _require_can_edit(user, group_id: int) -> None:
    """Members of the team can edit; so can admins, on the team's behalf."""
    _require_can_view(user, group_id)


def _require_unlocked(entry) -> None:
    if entry is not None and entry.is_locked:
        raise SubmissionLocked()


def _deadline_payload() -> dict:
    # Due when Notify Finalists says the slides are; shown, not enforced, so
    # the round stays open for now. The shape is the submission portal's.
    return {"closes_at": slides_due_at(), "is_extended": False, "is_open": True}


def _entry_data(entry) -> dict:
    return FinalistEntrySerializer(entry).data


def _write_result(entry) -> Response:
    return Response({"deadline": _deadline_payload(), "entry": _entry_data(entry)})


class FinalistEntryView(APIView):
    """Read the finalist entry, or submit the team's availability: the times,
    set on Management > Finalist Presentation, the whole team can make.
    Anyone on the team (students, mentors, supervisors) or an admin submits
    it; who and when is kept."""

    def get(self, request, group_id: int):
        group = _finalist_group(group_id)
        _require_can_view(request.user, group.id)
        entry = FinalistEntry.objects.filter(group=group).first()
        return Response({
            "group": {"id": group.id, "name": group.group_name},
            "deadline": _deadline_payload(),
            # This year's presentation times, as "9:30 – 10:00", once
            # Management shows them; until then none, and none are needed.
            "times_shown": times_shown(),
            "sessions": time_options() if times_shown() else [],
            "symposium_date": symposium_date(),
            "max_file_size": FINALIST_MAX_UPLOAD_SIZE,
            # None means the team has not started.
            "entry": _entry_data(entry) if entry is not None else None,
        })

    def put(self, request, group_id: int):
        group = _finalist_group(group_id)
        _require_can_edit(request.user, group.id)

        if not times_shown():
            raise TimesNotShown()
        payload = FinalistAvailabilitySerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        with transaction.atomic():
            entry, _ = FinalistEntry.objects.select_for_update().get_or_create(group=group)
            _require_unlocked(entry)
            submit_team_times(request.user, group, payload.validated_data["session_ids"])
            entry.save(update_fields=["updated_at"])
        return _write_result(entry)


class FinalistPresentationView(APIView):
    """Attach the presentation, or remove it again."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, group_id: int):
        group = _finalist_group(group_id)
        _require_can_edit(request.user, group.id)

        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise NoFileUploaded()
        validate_presentation_file(uploaded)

        entry, _ = FinalistEntry.objects.get_or_create(group=group)
        _require_unlocked(entry)
        previous = entry.presentation or {}

        # Removes the stored blob again if the save below raises.
        with _storage.stored_file(
            uploaded,
            content_type_field="mime",
            size_field="size",
            original_filename_field="name",
            storage_name=slides_file_name(group, uploaded.name),
        ) as file_data:
            entry.presentation = file_data
            entry.save(update_fields=["presentation", "updated_at"])

        previous_key = previous.get("storage_key")
        submitted_key = (entry.submitted_presentation or {}).get("storage_key")
        if previous_key and previous_key not in (file_data.get("storage_key"), submitted_key):
            _storage.delete(previous_key)
        return _write_result(entry)

    def delete(self, request, group_id: int):
        group = _finalist_group(group_id)
        _require_can_edit(request.user, group.id)

        entry = FinalistEntry.objects.filter(group=group).first()
        _require_unlocked(entry)
        existing = (entry.presentation or {}) if entry else {}
        if not existing:
            raise FileNotUploadedYet()

        entry.presentation = None
        entry.save(update_fields=["presentation", "updated_at"])
        key = existing.get("storage_key")
        if key and key != (entry.submitted_presentation or {}).get("storage_key"):
            _storage.delete(key)
        return _write_result(entry)


def _serve_presentation(request, group_id: int, *, as_attachment: bool):
    group = _finalist_group(group_id)
    _require_can_view(request.user, group.id)
    entry = FinalistEntry.objects.filter(group=group).first()
    stored = (entry.presentation or {}) if entry else {}
    if not stored.get("storage_key"):
        raise FileNotUploadedYet()
    if not as_attachment and not (stored.get("name") or "").lower().endswith(".pdf"):
        raise Http404("Only a PDF presentation can be previewed in the browser.")
    return serve_managed_file(
        resolve_url=_storage.resolve_url,
        open_file=_storage.open,
        storage_key=stored["storage_key"],
        filename=stored.get("name") or "presentation",
        mime_type=stored.get("mime"),
        size=stored.get("size"),
        as_attachment=as_attachment,
    )


class FinalistPresentationDownloadView(APIView):
    def get(self, request, group_id: int):
        return _serve_presentation(request, group_id, as_attachment=True)


class FinalistPresentationPreviewView(APIView):
    """Display a PDF presentation inline; PowerPoint files are download only."""

    # The page embeds this in a frame, which DENY would block when served locally.
    @method_decorator(xframe_options_exempt)
    def get(self, request, group_id: int):
        return _serve_presentation(request, group_id, as_attachment=False)


class FinalistSubmitView(APIView):
    def post(self, request, group_id: int):
        group = _finalist_group(group_id)
        _require_can_edit(request.user, group.id)

        with transaction.atomic():
            entry, _ = FinalistEntry.objects.select_for_update().get_or_create(group=group)
            if entry.is_locked:
                raise SubmissionLocked()
            # Only once the times are shown can the team give them.
            if times_shown() and not team_has_availability(group.id):
                raise AvailabilityRequired()
            if not entry.presentation:
                raise PresentationRequired()

            superseded = (entry.submitted_presentation or {}).get("storage_key")
            entry.snapshot(request.user)
            entry.save()
            # The Finalist Presentation tab's Finalist Submissions table.
            record_submitted_slides(entry)

        # Outside the transaction, since a blob delete cannot be rolled back.
        if superseded and superseded != (entry.presentation or {}).get("storage_key"):
            _storage.delete(superseded)
        return _write_result(entry)


class FinalistReopenView(APIView):
    """Reopen a submitted entry; the submitted copy stays until it is resubmitted."""

    def post(self, request, group_id: int):
        group = _finalist_group(group_id)
        _require_can_edit(request.user, group.id)

        entry = FinalistEntry.objects.filter(group=group).first()
        if entry is None or not entry.is_submitted:
            raise NotSubmittedYet()
        entry.reopened_at = timezone.now()
        entry.save(update_fields=["reopened_at", "updated_at"])
        return _write_result(entry)
