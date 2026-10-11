"""Completing an entry: shared by the Submit button and the automated submission."""
from .checklist import is_confirmed
from .models import Submission
from .serializers import missing_required_answers
from .services import active_deadline, current_cohort
from .storage import submission_file_service


def is_complete(submission: Submission) -> bool:
    """Everything Submit requires of a team: poster, title, every required answer and the checklist."""
    return bool(
        submission.poster
        and submission.project_title.strip()
        and not missing_required_answers(submission)
        and is_confirmed(submission.poster_checklist)
    )


def complete_submission(
    submission: Submission, user, *, automated: bool = False, cohort: int | None = None
) -> dict:
    """Freeze the entry as submitted; call inside the caller's transaction, holding the row.

    Returns the files the previous submission used, for ``delete_superseded`` once committed.
    """
    superseded = {
        slot: (getattr(submission, f"submitted_{slot}") or {}).get("storage_key")
        for slot in Submission.FILE_SLOTS
    }
    submission.snapshot(user)
    submission.auto_submitted = automated
    submission.cohort = cohort or current_cohort()
    # Late = past the global announced deadline, even inside the grace window or an extension.
    baseline = active_deadline()
    submission.is_late = baseline is not None and submission.submitted_at > baseline.closes_at
    submission.save()
    return superseded


def delete_superseded(submission: Submission, superseded: dict) -> None:
    """Remove files no longer referenced; after the commit, since a blob delete cannot be rolled back."""
    still_referenced = submission.submitted_storage_keys()
    for slot, key in superseded.items():
        if key and key not in still_referenced:
            submission_file_service(slot).delete(key)
