import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings
from rest_framework import status

from apps.common.storage import reset_managed_storage_caches
from apps.tickets.models import Ticket, TicketAttachment
from apps.tickets.services.attachments import ticket_files

User = get_user_model()

LIST_URL = "/api/v1/tickets/"
_MEDIA = tempfile.mkdtemp(prefix="ticket-commit-hook-tests-")


@override_settings(MEDIA_ROOT=_MEDIA)
class EmailHookFailureTests(TransactionTestCase):
    """An email that cannot be built must not destroy the ticket's attachments.

    TransactionTestCase on purpose: a plain TestCase never reaches a real
    COMMIT, and this whole failure lives in the window between the commit and
    the end of the view's attachment-cleanup scope. Django runs on_commit
    hooks from inside the transaction block's exit, so an exception from one
    of them unwinds through that cleanup after the rows are already durable.
    Marking the hooks robust is what closes it.
    """

    def setUp(self):
        reset_managed_storage_caches()
        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson",
            account_status=User.AccountStatus.ACTIVE,
        )
        self.client.force_login(self.requester)

    def tearDown(self):
        reset_managed_storage_caches()
        Ticket.objects.all().delete()

    def submit(self):
        return self.client.post(LIST_URL, {
            "category": "account_access",
            "subject": "With evidence attached",
            "body": "See the screenshot.",
            "files": SimpleUploadedFile(
                "evidence.pdf", b"%PDF-1.4" + b"0" * 256, content_type="application/pdf"
            ),
        }, format="multipart")

    def test_a_submission_survives_an_email_that_cannot_be_built(self):
        with patch(
            "apps.tickets.services.emails.send_ticket_submitted",
            side_effect=RuntimeError("template blew up"),
        ):
            response = self.submit()

        # The ticket was created. Failing the request would push the student
        # into submitting a second copy of the same problem.
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_the_attachment_is_still_there_afterwards(self):
        with patch(
            "apps.tickets.services.emails.send_ticket_submitted",
            side_effect=RuntimeError("template blew up"),
        ):
            self.submit()

        attachment = TicketAttachment.objects.get()
        # The row and the stored file have to agree. A committed row pointing
        # at a deleted blob is a download that 404s forever, for the student
        # and the agent alike.
        self.assertTrue(
            ticket_files.exists(attachment.storage_key),
            "the stored file was deleted even though its row committed",
        )

    def test_the_happy_path_still_stores_the_file(self):
        response = self.submit()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ticket_files.exists(TicketAttachment.objects.get().storage_key))
