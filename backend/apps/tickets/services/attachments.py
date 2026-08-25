"""Getting uploaded files into storage before the database hears about them.

Two rules drive the shape of this module:

The upload has to finish before the transaction opens. A blob write is a
network round-trip to Azure; doing it inside the transaction means one slow
upload holds a row lock for the duration.

A blob whose row never got written is litter nobody will ever find. So the
context manager below deletes what it stored if the caller raises on the way
to commit.
"""

from contextlib import ExitStack, contextmanager

from apps.common.storage import ManagedFileService, get_ticket_storage
from apps.common.upload_validation import validate_uploaded_file
from rest_framework import serializers

# D9. jpg and jpeg both spelled out because the validator matches on the
# literal suffix.
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = ("pdf", "png", "jpg", "jpeg", "docx")
ALLOWED_MIME_TYPES = (
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)
MAX_ATTACHMENTS_PER_MESSAGE = 5

ticket_files = ManagedFileService(get_ticket_storage)


def validate_attachments(files) -> None:
    """Reject the batch before anything is uploaded."""
    if len(files) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise serializers.ValidationError(
            f"Attach at most {MAX_ATTACHMENTS_PER_MESSAGE} files to one message."
        )
    for uploaded in files:
        validate_uploaded_file(
            uploaded,
            max_size=MAX_ATTACHMENT_BYTES,
            allowed_extensions=ALLOWED_EXTENSIONS,
            allowed_mime_types=ALLOWED_MIME_TYPES,
            field_label="Attachment",
        )


@contextmanager
def stored_attachments(files):
    """Upload every file, yielding rows ready for TicketAttachment.

    If the caller raises before it returns, every blob written here is removed
    on the way out.
    """
    files = list(files or ())
    validate_attachments(files)
    with ExitStack() as stack:
        rows = [
            stack.enter_context(
                ticket_files.stored_file(
                    uploaded,
                    content_type_field="mime_type",
                    size_field="size",
                    original_filename_field="original_filename",
                )
            )
            for uploaded in files
        ]
        yield rows
