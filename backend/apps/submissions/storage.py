from apps.common.filenames import year_file_name
from apps.common.storage import (
    ManagedFileService,
    get_poster_storage,
    get_prototype_storage,
    get_report_storage,
    get_slides_storage,
)


# One container per attachment slot (see AZURE_POSTER_CONTAINER and friends):
# competition entries stay out of the general resource library, and each kind
# of file is separated at the storage-account level.
SUBMISSION_FILE_SERVICES: dict[str, ManagedFileService] = {
    "poster": ManagedFileService(get_poster_storage),
    "report": ManagedFileService(get_report_storage),
    "prototype": ManagedFileService(get_prototype_storage),
}


# Finalists' presentation slides: uploaded on the finalist step, opened from
# the Finalist Presentation tab.
FINALIST_SLIDES_FILES = ManagedFileService(get_slides_storage)


# What each slot's file is called in its stored name.
_KINDS = {"poster": "Poster", "report": "Report", "prototype": "Prototype"}


def submission_file_name(submission, slot: str, original_filename: str | None) -> str:
    """Where an entry's file is stored, e.g. "2026_BTF01_Poster.pdf": its
    challenge year, its group and the slot, as the grading download names it.
    A name already taken (the submitted copy kept while the team revises) gets
    a random ending from storage, never overwritten."""
    return year_file_name(submission.cohort, submission.group.group_name, _KINDS[slot], original_filename)


def slides_file_name(group, original_filename: str | None) -> str:
    """Where a finalist's slides are stored, e.g. "2026_BTF01_Slides.pptx"."""
    return year_file_name(group.year, group.group_name, "Slides", original_filename)


def submission_file_service(slot: str) -> ManagedFileService:
    """The storage service for one attachment slot.

    KeyError on an unknown slot is deliberate: every caller works with a slot
    that already passed ``_valid_slot`` (views) or a component code from the
    grading catalogue, so an unknown value here is a programming error.
    """
    return SUBMISSION_FILE_SERVICES[slot]
