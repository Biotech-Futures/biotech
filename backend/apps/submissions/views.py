import hmac

from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import group_participant_qs, is_admin, user_has_role
from apps.common.role_names import ROLE_STUDENT
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
    StudentRoleRequired,
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
from .storage import SUBMISSION_FILE_SERVICE
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
    """Students on the team can read it; so can admins, for oversight.

    Mentors and supervisors are excluded although they are group members:
    neither is involved in assessment. Enforced here because the page is
    reachable by URL, so hiding the nav entry would not be enough.
    """
    if is_admin(user):
        return
    if not group_participant_qs(user, group_id).exists():
        raise GroupAccessDenied()
    if not user_has_role(user, ROLE_STUDENT):
        raise StudentRoleRequired()


def _require_can_edit(user, group_id: int) -> None:
    """Editing is limited to students on the team.

    Admins can view an entry but not author it, so a submission always reflects
    what the team wrote. If mentors are ever allowed to submit, change it here.
    """
    if not group_participant_qs(user, group_id).exists():
        raise GroupAccessDenied()
    if not user_has_role(user, ROLE_STUDENT):
        raise StudentRoleRequired()


def _require_unlocked(submission) -> None:
    """Refuse edits to an entry that has been submitted.

    Reopening is deliberate, so a submitted entry cannot drift through stray
    saves or uploads.
    """
    if submission is not None and submission.is_locked:
        raise SubmissionLocked()


def _require_open(group_id: int):
    """Reject writes once the team's deadline has passed.

    The page's countdown is convenience; only the server decides.
    """
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
            # The form renders whatever is returned here, so rewording a
            # question is an admin edit rather than a deploy.
            "questions": SubmissionQuestionSerializer(
                SubmissionQuestion.active(), many=True
            ).data,
            # Keyed by section; a missing section simply renders nothing.
            "instructions": {
                instruction.section: {
                    "heading": instruction.heading,
                    "body": instruction.body,
                }
                for instruction in SubmissionInstruction.objects.all()
            },
            # Published so the page can state each limit and refuse an
            # oversized file early. The server still enforces them.
            "max_file_sizes": max_sizes(),
            # None means the team has not started; the page renders an empty
            # form rather than an error.
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

        # Locked for the read-modify-write below, or two teammates auto-saving
        # at once would have the second silently discard the first.
        with transaction.atomic():
            submission, _ = (
                Submission.objects.select_for_update().get_or_create(group=group)
            )
            _require_unlocked(submission)

            # Only fields the client sent, so updating the link cannot blank
            # the answers by omitting them.
            if "answers" in data:
                # Merged, not replaced, so teammates on different questions do
                # not overwrite each other. Clearing needs an explicit "".
                submission.answers = {**(submission.answers or {}), **data["answers"]}
            if "prototype_url" in data:
                submission.prototype_url = data["prototype_url"]
            submission.save()

        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })


def _valid_slot(slot: str) -> str:
    # 404, not 400: an unknown slot is a URL that does not exist.
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

        # Checked at upload, not at submit, so a team finds out while the file
        # is still in front of them.
        poster_flag = None
        if slot == POSTER:
            checks = inspect_poster(uploaded, team_code=group.group_name)
            if checks.blocking:
                # Only findings a student can verify are named; the rest
                # become one general instruction.
                raise PosterFormatRejected(student_facing_problems(checks.blocking))
            poster_flag = checks.as_flag()

        submission, _ = Submission.objects.get_or_create(group=group)
        _require_unlocked(submission)
        previous = getattr(submission, slot) or {}

        # Writes the blob first and removes it if anything below raises, so a
        # failed save cannot strand a file with no record pointing at it.
        with SUBMISSION_FILE_SERVICE.stored_file(
            uploaded,
            content_type_field="mime",
            size_field="size",
            original_filename_field="name",
        ) as file_data:
            setattr(submission, slot, file_data)
            # Written with the file it describes, so the two cannot disagree
            # about which poster is on record.
            fields = [slot, "updated_at"]
            if slot == POSTER:
                submission.poster_checks = poster_flag
                fields.append("poster_checks")
            submission.save(update_fields=fields)

        # Old file discarded only once the new one is recorded. A file the
        # submitted copy still points at is kept regardless.
        previous_key = previous.get("storage_key")
        if (
            previous_key
            and previous_key != file_data.get("storage_key")
            and previous_key not in submission.submitted_storage_keys()
        ):
            SUBMISSION_FILE_SERVICE.delete(previous_key)

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
        # Cleared with the file, or findings would describe a poster that is
        # no longer attached.
        fields = [slot, "updated_at"]
        if slot == POSTER:
            submission.poster_checks = None
            fields.append("poster_checks")
        submission.save(update_fields=fields)
        # Kept if the submitted copy still references it — see the upload path.
        key = existing.get("storage_key")
        if key and key not in submission.submitted_storage_keys():
            SUBMISSION_FILE_SERVICE.delete(key)

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

    return serve_managed_file(
        resolve_url=SUBMISSION_FILE_SERVICE.resolve_url,
        open_file=SUBMISSION_FILE_SERVICE.open,
        storage_key=stored["storage_key"],
        filename=stored.get("name") or f"{slot}",
        mime_type=stored.get("mime"),
        size=stored.get("size"),
        as_attachment=as_attachment,
    )


class GroupSubmissionFileDownloadView(APIView):
    """Download one attachment. Readable by anyone who may read the entry."""

    def get(self, request, group_id: int, slot: str):
        return _serve_slot(request, group_id, _valid_slot(slot), as_attachment=True)


class GroupSubmissionFilePreviewView(APIView):
    """Display an attachment in the browser rather than downloading it.

    PDF slots only: those are checked byte-for-byte at upload. The prototype
    accepts any type, and inline HTML or SVG would execute in the viewer's
    session. Making it a property of the URL keeps that boundary explicit.
    """

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

        # Submitting writes every column back, so without the lock a teammate's
        # auto-save landing mid-submit is reverted and lost from the snapshot.
        with transaction.atomic():
            submission, _ = (
                Submission.objects.select_for_update().get_or_create(group=group)
            )
            if submission.is_locked:
                # Submitted and not reopened: resubmitting is an explicit
                # step, so this is a mistake rather than a no-op.
                raise SubmissionLocked()

            # The competition's core deliverable, checked server-side so it
            # cannot be clicked past.
            if not submission.poster:
                raise PosterRequired()

            # Enforced only here, so a team can save a half-finished draft.
            missing = missing_required_answers(submission)
            if missing:
                raise RequiredAnswersMissing(missing)

            # Files the previous submission relied on, taken before the
            # snapshot overwrites them.
            superseded = submission.submitted_storage_keys()

            submission.snapshot(request.user)
            # Stamped at submit: a draft may predate the deadline row, and the
            # cohort has to be the competition's year.
            submission.cohort = current_cohort()
            # Always False while post-deadline writes are refused; kept because
            # it records the state at submit time.
            submission.is_late = False
            submission.save()

        # Outside the transaction: a blob delete cannot be rolled back, so a
        # later failure would leave the row pointing at a missing file.
        for key in superseded - submission.submitted_storage_keys():
            SUBMISSION_FILE_SERVICE.delete(key)

        # After the snapshot, so the email describes what was recorded. Never
        # raises: a failed send must not fail the submission.
        send_submission_confirmation(submission)

        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })


class GroupSubmissionReopenView(APIView):
    """Reopen a submitted entry for revision.

    The submitted copy is replaced only when a new submission completes, so a
    team that reopens and runs out of time still has what they submitted.
    """

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
    """Trigger the daily reminder run. Called by a scheduler, not a person.

    Guarded by a shared secret because the caller has no session; the same
    shape as the RSVP trigger next door. An unset token answers 503 rather than
    leaving an open endpoint that could email every team.
    """

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
