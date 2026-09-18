import hmac

from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import group_participant_qs, is_admin
from apps.common.storage import serve_managed_file
from apps.groups.models import Groups
from config.errors import GroupAccessDenied

from .emails import send_submission_confirmation
from .errors import (
    FileNotUploadedYet,
    NoFileUploaded,
    NotSubmittedYet,
    PosterFormatRejected,
    PosterRequired,
    RequiredAnswersMissing,
    SubmissionLocked,
    SubmissionsClosed,
    SubmissionsNotConfigured,
)
from .models import Submission, SubmissionInstruction, SubmissionQuestion
from .poster_checks import inspect_poster, student_facing_problems
from .reminders import send_due_reminders
from .serializers import (
    SubmissionDraftSerializer,
    SubmissionQuestionSerializer,
    SubmissionSerializer,
    missing_required_answers,
)
from .services import current_cohort, deadline_for_group
from .storage import submission_file_service
from .uploads import (
    PDF_SLOTS,
    POSTER,
    SLOTS,
    max_sizes,
    validate_submission_file,
)


def _get_group(group_id: int) -> Groups:
    return get_object_or_404(Groups, id=group_id, deleted_at__isnull=True)


def _require_can_view(user, group_id: int) -> None:
    """Any member of the team can read it; so can admins.

    Staff and superusers pass alongside AdminScope admins so the definition
    matches grading's ``IsGrader``: anyone who can mark an entry can read the
    files they are marking.
    """
    if is_admin(user) or user.is_staff or user.is_superuser:
        return
    if not group_participant_qs(user, group_id).exists():
        raise GroupAccessDenied()


def _require_can_edit(user, group_id: int) -> None:
    """Only members of the team can edit; admins can view but not author."""
    if not group_participant_qs(user, group_id).exists():
        raise GroupAccessDenied()


def _require_unlocked(submission) -> None:
    if submission is not None and submission.is_locked:
        raise SubmissionLocked()


def _require_open(group_id: int):
    info = deadline_for_group(group_id)
    if info.closes_at is None:
        raise SubmissionsNotConfigured()
    if not info.is_open:
        raise SubmissionsClosed()
    return info


def _deadline_payload(group_id: int) -> dict:
    info = deadline_for_group(group_id)
    return {
        "closes_at": info.closes_at,
        "is_extended": info.is_extended,
        "is_open": info.is_open,
    }


class GroupSubmissionView(APIView):
    """Read or draft-save one team's submission."""

    def get(self, request, group_id: int):
        group = _get_group(group_id)
        _require_can_view(request.user, group.id)

        submission = Submission.objects.filter(group=group).first()
        return Response({
            "group": {"id": group.id, "name": group.group_name},
            "deadline": _deadline_payload(group.id),
            "questions": SubmissionQuestionSerializer(
                SubmissionQuestion.active(), many=True
            ).data,
            "instructions": {
                instruction.section: {
                    "heading": instruction.heading,
                    "body": instruction.body,
                }
                for instruction in SubmissionInstruction.objects.all()
            },
            "max_file_sizes": max_sizes(),
            # None means the team has not started.
            "submission": (
                SubmissionSerializer(submission).data if submission is not None else None
            ),
        })

    def put(self, request, group_id: int):
        group = _get_group(group_id)
        _require_can_edit(request.user, group.id)
        _require_open(group.id)

        payload = SubmissionDraftSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        # Locked so two teammates auto-saving at once cannot overwrite each other.
        with transaction.atomic():
            submission, _ = (
                Submission.objects.select_for_update().get_or_create(group=group)
            )
            _require_unlocked(submission)

            if "answers" in data:
                # Merged, not replaced, so teammates on different questions do not collide.
                submission.answers = {**(submission.answers or {}), **data["answers"]}
            if "prototype_url" in data:
                submission.prototype_url = data["prototype_url"]
            submission.save()

        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })


def _valid_slot(slot: str) -> str:
    if slot not in SLOTS:
        raise Http404(f"Unknown attachment slot '{slot}'.")
    return slot


class GroupSubmissionFileView(APIView):
    """Attach a file to one slot, or remove it again."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, group_id: int, slot: str):
        slot = _valid_slot(slot)
        group = _get_group(group_id)
        _require_can_edit(request.user, group.id)
        _require_open(group.id)

        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise NoFileUploaded()
        validate_submission_file(uploaded, slot)

        poster_flag = None
        if slot == POSTER and settings.SUBMISSION_POSTER_CHECKS_ENABLED:
            checks = inspect_poster(uploaded, team_code=group.group_name)
            if checks.blocking:
                # One at a time, so several problems never read as one paragraph.
                raise PosterFormatRejected(student_facing_problems(checks.blocking)[:1])
            poster_flag = checks.as_flag()

        submission, _ = Submission.objects.get_or_create(group=group)
        _require_unlocked(submission)
        previous = getattr(submission, slot) or {}

        # Removes the stored blob again if the save below raises.
        with submission_file_service(slot).stored_file(
            uploaded,
            content_type_field="mime",
            size_field="size",
            original_filename_field="name",
        ) as file_data:
            setattr(submission, slot, file_data)
            fields = [slot, "updated_at"]
            if slot == POSTER:
                submission.poster_checks = poster_flag
                fields.append("poster_checks")
            submission.save(update_fields=fields)

        # A file the submitted copy still points at is kept.
        previous_key = previous.get("storage_key")
        if (
            previous_key
            and previous_key != file_data.get("storage_key")
            and previous_key not in submission.submitted_storage_keys()
        ):
            submission_file_service(slot).delete(previous_key)

        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })

    def delete(self, request, group_id: int, slot: str):
        slot = _valid_slot(slot)
        group = _get_group(group_id)
        _require_can_edit(request.user, group.id)
        _require_open(group.id)

        submission = Submission.objects.filter(group=group).first()
        _require_unlocked(submission)
        existing = (getattr(submission, slot) or {}) if submission else {}
        if not existing:
            raise FileNotUploadedYet()

        setattr(submission, slot, None)
        fields = [slot, "updated_at"]
        if slot == POSTER:
            submission.poster_checks = None
            fields.append("poster_checks")
        submission.save(update_fields=fields)
        key = existing.get("storage_key")
        if key and key not in submission.submitted_storage_keys():
            submission_file_service(slot).delete(key)

        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })


def _serve_slot(request, group_id: int, slot: str, *, as_attachment: bool):
    group = _get_group(group_id)
    _require_can_view(request.user, group.id)

    submission = Submission.objects.filter(group=group).first()
    stored = (getattr(submission, slot) or {}) if submission else {}
    if not stored.get("storage_key"):
        raise FileNotUploadedYet()

    service = submission_file_service(slot)
    return serve_managed_file(
        resolve_url=service.resolve_url,
        open_file=service.open,
        storage_key=stored["storage_key"],
        filename=stored.get("name") or f"{slot}",
        mime_type=stored.get("mime"),
        size=stored.get("size"),
        as_attachment=as_attachment,
    )


class GroupSubmissionFileDownloadView(APIView):
    def get(self, request, group_id: int, slot: str):
        return _serve_slot(request, group_id, _valid_slot(slot), as_attachment=True)


class GroupSubmissionFilePreviewView(APIView):
    """Display a PDF attachment inline; other types could run scripts in the viewer's session."""

    # The page embeds this in a frame, which DENY would block when served locally.
    @method_decorator(xframe_options_exempt)
    def get(self, request, group_id: int, slot: str):
        if slot not in PDF_SLOTS:
            raise Http404(f"'{slot}' cannot be previewed in the browser.")
        return _serve_slot(request, group_id, slot, as_attachment=False)


class GroupSubmissionSubmitView(APIView):
    """Complete a submission, taking a copy of what was submitted."""

    def post(self, request, group_id: int):
        group = _get_group(group_id)
        _require_can_edit(request.user, group.id)
        _require_open(group.id)

        # Locked so a teammate's auto-save cannot land mid-submit and be lost.
        with transaction.atomic():
            submission, _ = (
                Submission.objects.select_for_update().get_or_create(group=group)
            )
            if submission.is_locked:
                raise SubmissionLocked()

            if not submission.poster:
                raise PosterRequired()

            # Enforced only at submit, so a half-finished draft can still be saved.
            missing = missing_required_answers(submission)
            if missing:
                raise RequiredAnswersMissing(missing)

            # Files the previous submission relied on, taken before the
            # snapshot overwrites them. Kept per slot: each slot stores into
            # its own container, so a delete must know where the key lives.
            superseded = {
                slot: (getattr(submission, f"submitted_{slot}") or {}).get("storage_key")
                for slot in Submission.FILE_SLOTS
            }

            submission.snapshot(request.user)
            submission.cohort = current_cohort()
            submission.is_late = False
            submission.save()

        # Outside the transaction, since a blob delete cannot be rolled back.
        still_referenced = submission.submitted_storage_keys()
        for slot, key in superseded.items():
            if key and key not in still_referenced:
                submission_file_service(slot).delete(key)

        # Never raises, so a failed email cannot fail the submission.
        send_submission_confirmation(submission)

        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })


class GroupSubmissionReopenView(APIView):
    """Reopen a submitted entry; the submitted copy stays until it is resubmitted."""

    def post(self, request, group_id: int):
        group = _get_group(group_id)
        _require_can_edit(request.user, group.id)
        _require_open(group.id)

        submission = Submission.objects.filter(group=group).first()
        if submission is None or not submission.is_submitted:
            raise NotSubmittedYet()

        submission.reopened_at = timezone.now()
        submission.save(update_fields=["reopened_at", "updated_at"])

        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })


class SendSubmissionRemindersView(APIView):
    """Daily reminder run, called by a scheduler with a shared token."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        expected = getattr(settings, "SUBMISSION_REMINDER_TOKEN", "") or ""
        if not expected:
            return Response(
                {"detail": "Submission reminder trigger is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        provided = request.headers.get("X-Reminder-Token", "")
        if not hmac.compare_digest(provided, expected):
            return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(send_due_reminders(), status=status.HTTP_200_OK)
