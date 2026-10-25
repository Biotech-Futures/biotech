"""What a ticket attachment has to be before it is stored.

The batch rules live in ``services/attachments`` rather than in a serializer
because the three endpoints that take ticket files read ``request.FILES``
themselves. Anything the DRF ``FileField`` would have refused on the way in
has to be refused here instead, and the empty file is the one that was not.
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import serializers

from apps.tickets.services.attachments import (
    MAX_ATTACHMENTS_PER_MESSAGE,
    validate_attachments,
)


def pdf(name="note.pdf", body=b"%PDF-1.4" + b"0" * 128):
    return SimpleUploadedFile(name, body, content_type="application/pdf")


class EmptyAttachmentTests(TestCase):
    """A 0 byte file was taken, stored and shown as an ordinary attachment.

    Both ends saw a filename and a link, and the link downloaded nothing. The
    student who attached the wrong thing had no way to tell, and the agent
    opened an empty file. Chat and the resource library have refused this all
    along, through the FileField their serializers use.
    """

    def test_an_empty_file_is_refused(self):
        with self.assertRaises(serializers.ValidationError) as caught:
            validate_attachments([pdf(body=b"")])
        self.assertIn("empty", str(caught.exception).lower())

    def test_one_empty_file_refuses_the_whole_batch(self):
        """Whichever position it arrives in. The loop is over the batch, and
        a rule applied to the first file only is a rule an attacker or an
        unlucky student walks past by attaching two."""
        for position in range(MAX_ATTACHMENTS_PER_MESSAGE):
            batch = [pdf(f"real{n}.pdf") for n in range(MAX_ATTACHMENTS_PER_MESSAGE)]
            batch[position] = pdf("empty.pdf", body=b"")
            with self.subTest(position=position):
                with self.assertRaises(serializers.ValidationError):
                    validate_attachments(batch)

    def test_a_file_with_content_is_still_accepted(self):
        """The bound is a lower one, not a ban. A one byte file is a real
        file."""
        validate_attachments([pdf(), pdf("tiny.pdf", body=b"%")])

    def test_no_files_at_all_is_still_fine(self):
        """Most messages carry none."""
        validate_attachments([])
