from apps.common.storage import (
    ManagedFileService,
    get_poster_storage,
    get_prototype_storage,
    get_report_storage,
)


# One container per attachment slot (see AZURE_POSTER_CONTAINER and friends):
# competition entries stay out of the general resource library, and each kind
# of file is separated at the storage-account level.
SUBMISSION_FILE_SERVICES: dict[str, ManagedFileService] = {
    "poster": ManagedFileService(get_poster_storage),
    "report": ManagedFileService(get_report_storage),
    "prototype": ManagedFileService(get_prototype_storage),
}


def submission_file_service(slot: str) -> ManagedFileService:
    """The storage service for one attachment slot.

    KeyError on an unknown slot is deliberate: every caller works with a slot
    that already passed ``_valid_slot`` (views) or a component code from the
    grading catalogue, so an unknown value here is a programming error.
    """
    return SUBMISSION_FILE_SERVICES[slot]
