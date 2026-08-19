from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import group_participant_qs, is_admin, user_has_role
from apps.common.role_names import ROLE_STUDENT
from apps.common.storage import serve_managed_file
from apps.groups.models import Groups
from config.errors import GroupAccessDenied

from .errors import (
    FileNotUploadedYet,
    NoFileUploaded,
    PosterRequired,
    RequiredAnswersMissing,
    StudentRoleRequired,
    SubmissionsClosed,
    SubmissionsNotConfigured,
)
from .models import Submission, SubmissionQuestion
from .serializers import (
    SubmissionDraftSerializer,
    SubmissionQuestionSerializer,
    SubmissionSerializer,
    missing_required_answers,
)
from .services import deadline_for_group
from .storage import SUBMISSION_FILE_SERVICE
from .uploads import PDF_SLOTS, SLOTS, max_sizes, validate_submission_file


def _get_group(group_id: int) -> Groups:
    return get_object_or_404(Groups, id=group_id, deleted_at__isnull=True)


def _require_can_view(user, group_id: int) -> None:
    """Members of the team can read it; so can admins, for oversight."""
    if is_admin(user):
        return
    if not group_participant_qs(user, group_id).exists():
        raise GroupAccessDenied()


def _require_can_edit(user, group_id: int) -> None:
    """Editing is limited to students on the team.

    Admins are deliberately excluded: they can view an entry but not author it,
    so a submission always reflects what the team themselves wrote. Whether
    mentors should be able to submit on a team's behalf is an open question
    with the client — if the answer is yes, the role check below is where it
    changes.
    """
    if not group_participant_qs(user, group_id).exists():
        raise GroupAccessDenied()
    if not user_has_role(user, ROLE_STUDENT):
        raise StudentRoleRequired()


def _require_open(group_id: int):
    """Reject writes once the team's deadline has passed.

    Enforced here rather than in the browser: the frontend shows a countdown
    for convenience, but only the server decides whether a write is accepted.
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
            # The form renders whatever is returned here, so rewording or
            # reordering a question is an admin edit rather than a deploy.
            "questions": SubmissionQuestionSerializer(
                SubmissionQuestion.active(), many=True
            ).data,
            # Published so the page can state each limit and refuse an
            # oversized file before uploading it. Hardcoding the numbers in the
            # frontend would give two places to change and an eventual
            # mismatch; the server still enforces them either way.
            "max_file_sizes": max_sizes(),
            # None means the team has not started yet — the page renders an
            # empty form rather than treating it as an error.
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

        submission, _ = Submission.objects.get_or_create(group=group)
        # Only touch fields the client actually sent, so a client updating the
        # link cannot blank out the answers by omitting them.
        if "answers" in data:
            submission.answers = data["answers"]
        if "prototype_url" in data:
            submission.prototype_url = data["prototype_url"]
        submission.save()

        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })


def _valid_slot(slot: str) -> str:
    # 404 rather than 400: an unknown slot is a URL that does not exist, not a
    # badly-formed request to one that does.
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

        submission, _ = Submission.objects.get_or_create(group=group)
        previous = getattr(submission, slot) or {}

        # stored_file writes the blob first and removes it again if anything
        # below raises, so a failed save cannot strand a file with no record
        # pointing at it.
        with SUBMISSION_FILE_SERVICE.stored_file(
            uploaded,
            content_type_field="mime",
            size_field="size",
            original_filename_field="name",
        ) as file_data:
            setattr(submission, slot, file_data)
            submission.save(update_fields=[slot, "updated_at"])

        # Only once the new file is safely recorded is the old one discarded —
        # the reverse order would risk losing both.
        previous_key = previous.get("storage_key")
        if previous_key and previous_key != file_data.get("storage_key"):
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
        existing = (getattr(submission, slot) or {}) if submission else {}
        if not existing:
            raise FileNotUploadedYet()

        setattr(submission, slot, None)
        submission.save(update_fields=[slot, "updated_at"])
        SUBMISSION_FILE_SERVICE.delete(existing.get("storage_key"))

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

    Restricted to the PDF slots. Those files have been checked byte-for-byte at
    upload, so rendering them inline is safe; the prototype slot accepts any
    type, and displaying arbitrary uploaded content inline is how an HTML or
    SVG file ends up executing scripts in the viewer's session. Enforcing that
    by which slots this endpoint accepts — rather than a flag on the download
    endpoint — keeps the boundary a property of the URL.
    """

    def get(self, request, group_id: int, slot: str):
        if slot not in PDF_SLOTS:
            raise Http404(f"'{slot}' cannot be previewed in the browser.")
        return _serve_slot(request, group_id, slot, as_attachment=False)


class GroupSubmissionSubmitView(APIView):
    """Mark a team's entry as submitted. Re-submitting simply updates it."""

    def post(self, request, group_id: int):
        group = _get_group(group_id)
        _require_can_edit(request.user, group.id)
        _require_open(group.id)

        submission, _ = Submission.objects.get_or_create(group=group)
        # The poster is the competition's core deliverable, so an entry without
        # one is incomplete rather than merely sparse. Checked here rather than
        # in the browser so it cannot be clicked past.
        if not submission.poster:
            raise PosterRequired()

        # Required questions are enforced only at this point, so a team can
        # save a half-finished draft and come back to it.
        missing = missing_required_answers(submission)
        if missing:
            raise RequiredAnswersMissing(missing)

        submission.submitted_at = timezone.now()
        submission.submitted_by = request.user
        # Always False while writes are refused after the deadline. The field
        # is kept because it records the state at the time of submitting, which
        # matters if a grace period is ever introduced.
        submission.is_late = False
        submission.save()

        return Response({
            "deadline": _deadline_payload(group.id),
            "submission": SubmissionSerializer(submission).data,
        })
