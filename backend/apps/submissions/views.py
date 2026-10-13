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

from apps.common import email_jobs
from apps.common.rbac import group_participant_qs, is_admin
from apps.common.storage import serve_managed_file
from apps.groups.models import Groups
from apps.live.broadcast import notify_changed
from config.errors import GroupAccessDenied

from .emails import send_submission_confirmation
from .errors import (
    FileNotUploadedYet,
    NoFileUploaded,
    NotSubmittedYet,
    PosterChecklistIncomplete,
    PosterFormatRejected,
    PosterRequired,
    ProjectTitleRequired,
    RequiredAnswersMissing,
    SubmissionLocked,
    SubmissionsClosed,
    SubmissionsNotConfigured,
)
from .models import Submission, SubmissionInstruction, SubmissionQuestion
from .poster_checks import inspect_poster, student_facing_problems
from .autosubmit import auto_submit_due
from .reminders import send_due_reminders
from .serializers import (
    SubmissionDraftSerializer,
    SubmissionQuestionSerializer,
    SubmissionSerializer,
    missing_required_answers,
)
from .services import deadline_for_group
from .checklist import blank_checklist, detected_checklist, is_confirmed
from .submitting import complete_submission, delete_superseded
from .storage import submission_file_name, submission_file_service
from .uploads import (
    PDF_SLOTS,
    POSTER,
    SLOTS,
    max_sizes,
    validate_submission_file,
)


def _get_group(group_id: int) -> Groups:
    return get_object_or_404(Groups, id=group_id, deleted_at__isnull=True)


def _is_staff(user) -> bool:
    """Admins, staff and superusers, matching ``common.rbac.IsStaffOrAdmin``."""
    return is_admin(user) or user.is_staff or user.is_superuser


def _require_can_view(user, group_id: int) -> None:
    """Any member of the team can read it; so can admins, so anyone who marks an entry can read it."""
    if _is_staff(user):
        return
    if not group_participant_qs(user, group_id).exists():
        raise GroupAccessDenied()


def _require_can_edit(user, group_id: int) -> None:
    """Members of the team can edit, submit and reopen; so can admins, for a team that needs a hand."""
    _require_can_view(user, group_id)


def _require_unlocked(submission, user) -> None:
    """A submitted entry is read-only for its team; admins edit it without reopening it."""
    if submission is not None and submission.is_locked and not _is_staff(user):
        raise SubmissionLocked()


def _require_open(group_id: int, user):
    """The team's deadline, extensions included; admins act for a team at any time."""
    info = deadline_for_group(group_id)
    if _is_staff(user):
        return info
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
            # Admins act for a team at any time, without the template checks or checklist.
            "admin_access": _is_staff(request.user),
            # None means the team has not started.
            "submission": (
                SubmissionSerializer(submission).data if submission is not None else None
            ),
        })

    def put(self, request, group_id: int):
        group = _get_group(group_id)
        _require_can_edit(request.user, group.id)
        _require_open(group.id, request.user)

        payload = SubmissionDraftSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        # Locked so two teammates auto-saving at once cannot overwrite each other.
        with transaction.atomic():
            submission, _ = (
                Submission.objects.select_for_update().get_or_create(group=group)
            )
            _require_unlocked(submission, request.user)

            if "project_title" in data:
                submission.project_title = data["project_title"]
            if "answers" in data:
                # Merged, not replaced, so teammates on different questions do not collide.
                submission.answers = {**(submission.answers or {}), **data["answers"]}
            if "prototype_url" in data:
                submission.prototype_url = data["prototype_url"]
            if "poster_checklist" in data:
                # The team's ticks always stand, whatever the checks detected.
                submission.poster_checklist = {
                    **blank_checklist(), **(submission.poster_checklist or {}), **data["poster_checklist"]
                }
            submission.save()

        # Open pages catch up on what live text does not carry: an admin's save, ticks and the link.
        if _is_staff(request.user):
            notify_changed("submission", group.id, "draft", by=request.user)
        elif "poster_checklist" in data:
            notify_changed("submission", group.id, "checklist", by=request.user)
        elif "prototype_url" in data:
            notify_changed("submission", group.id, "link", by=request.user)

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
        _require_open(group.id, request.user)

        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise NoFileUploaded()
        validate_submission_file(uploaded, slot)

        poster_flag = None
        checks = None
        if slot == POSTER and settings.SUBMISSION_POSTER_CHECKS_ENABLED:
            checks = inspect_poster(uploaded, team_code=group.group_name)
            if checks.blocking and not _is_staff(request.user):
                # One at a time, so several problems never read as one paragraph.
                raise PosterFormatRejected(student_facing_problems(checks.blocking)[:1])
            poster_flag = checks.as_flag()

        submission, _ = Submission.objects.get_or_create(group=group)
        _require_unlocked(submission, request.user)

        # Removes the stored blob again if the save below raises.
        with submission_file_service(slot).stored_file(
            uploaded,
            content_type_field="mime",
            size_field="size",
            original_filename_field="name",
            storage_name=submission_file_name(submission, slot, uploaded.name),
        ) as file_data, transaction.atomic():
            # Read again under the lock, in case the entry was submitted while the file uploaded.
            submission = Submission.objects.select_for_update().get(pk=submission.pk)
            _require_unlocked(submission, request.user)
            previous = getattr(submission, slot) or {}
            setattr(submission, slot, file_data)
            fields = [slot, "updated_at"]
            if slot == POSTER:
                submission.poster_checks = poster_flag
                submission.poster_checklist = detected_checklist(checks)
                fields += ["poster_checks", "poster_checklist"]
            submission.save(update_fields=fields)

        # A file the submitted copy still points at is kept.
        previous_key = previous.get("storage_key")
        if (
            previous_key
            and previous_key != file_data.get("storage_key")
            and previous_key not in submission.submitted_storage_keys()
        ):
            submission_file_service(slot).delete(previous_key)

        notify_changed("submission", group.id, "files", by=request.user)
        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })

    def delete(self, request, group_id: int, slot: str):
        slot = _valid_slot(slot)
        group = _get_group(group_id)
        _require_can_edit(request.user, group.id)
        _require_open(group.id, request.user)

        with transaction.atomic():
            submission = Submission.objects.select_for_update().filter(group=group).first()
            _require_unlocked(submission, request.user)
            existing = (getattr(submission, slot) or {}) if submission else {}
            if not existing:
                raise FileNotUploadedYet()

            setattr(submission, slot, None)
            fields = [slot, "updated_at"]
            if slot == POSTER:
                submission.poster_checks = None
                submission.poster_checklist = blank_checklist()
                fields += ["poster_checks", "poster_checklist"]
            submission.save(update_fields=fields)
        key = existing.get("storage_key")
        if key and key not in submission.submitted_storage_keys():
            submission_file_service(slot).delete(key)

        notify_changed("submission", group.id, "files", by=request.user)
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
        _require_open(group.id, request.user)

        # Locked so a teammate's auto-save cannot land mid-submit and be lost.
        with transaction.atomic():
            submission, _ = (
                Submission.objects.select_for_update().get_or_create(group=group)
            )
            staff = _is_staff(request.user)
            if submission.is_locked and not staff:
                raise SubmissionLocked()

            if not submission.poster:
                raise PosterRequired()

            if not submission.project_title.strip():
                raise ProjectTitleRequired()

            # Enforced only at submit, so a half-finished draft can still be saved.
            missing = missing_required_answers(submission)
            if missing:
                raise RequiredAnswersMissing(missing)

            if not staff and not is_confirmed(submission.poster_checklist):
                raise PosterChecklistIncomplete()

            superseded = complete_submission(
                submission, request.user, cohort=group.year if staff else None
            )

        delete_superseded(submission, superseded)

        # Never raises, so a failed email cannot fail the submission.
        send_submission_confirmation(submission)

        notify_changed("submission", group.id, "submitted", by=request.user)
        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })


class GroupSubmissionReopenView(APIView):
    """Reopen a submitted entry; the submitted copy stays until it is resubmitted."""

    def post(self, request, group_id: int):
        group = _get_group(group_id)
        _require_can_edit(request.user, group.id)
        _require_open(group.id, request.user)

        submission = Submission.objects.filter(group=group).first()
        if submission is None or not submission.is_submitted:
            raise NotSubmittedYet()

        submission.reopened_at = timezone.now()
        submission.save(update_fields=["reopened_at", "updated_at"])

        notify_changed("submission", group.id, "reopened", by=request.user)
        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })


class SendSubmissionRemindersView(APIView):
    """Daily reminder run, called by a scheduler with the email jobs' token."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        return email_jobs.refused(request) or Response(send_due_reminders(), status=status.HTTP_200_OK)


class AutoSubmitView(APIView):
    """Hourly run submitting complete drafts past their cut-off, called by a scheduler with the jobs' token."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        return email_jobs.refused(request) or Response(auto_submit_due(), status=status.HTTP_200_OK)
