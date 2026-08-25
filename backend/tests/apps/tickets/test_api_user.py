import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.storage import reset_managed_storage_caches
from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
    TicketMessageType,
)
from apps.tickets.services import lifecycle

User = get_user_model()

LIST_URL = "/api/v1/tickets/"

_MEDIA = tempfile.mkdtemp(prefix="ticket-tests-")


def pdf(name="report.pdf", size=1024):
    return SimpleUploadedFile(name, b"%PDF-1.4" + b"0" * size, content_type="application/pdf")


@override_settings(MEDIA_ROOT=_MEDIA)
class UserTicketAPITestCase(APITestCase):
    def setUp(self):
        reset_managed_storage_caches()
        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson",
        )
        self.stranger = User.objects.create_user(
            email="someone@example.com", password="pass1234",
            first_name="Alex", last_name="Doe",
        )
        self.agent = User.objects.create_user(
            email="agent@example.com", password="pass1234",
            first_name="Sam", last_name="Reid",
        )
        SupportScope.objects.create(user=self.agent)
        self.client.force_login(self.requester)

    def tearDown(self):
        reset_managed_storage_caches()

    def make_ticket(self, owner=None, subject="Cannot access group workspace"):
        return lifecycle.create_ticket(
            user=owner or self.requester,
            category=TicketCategory.PROGRAMS_GROUPS,
            subject=subject,
            body="I get an error opening my group.",
        )


class TicketSubmissionTests(UserTicketAPITestCase):
    def test_submitting_a_ticket_returns_it_with_a_number(self):
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "Cannot sign in",
            "body": "The login code never arrives.",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()["data"]
        self.assertRegex(data["ticketNumber"], r"^SUP-\d{4}-\d{5}$")
        self.assertEqual(data["status"], "open")

    def test_the_timeline_comes_back_with_the_message_and_the_acknowledgement(self):
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "Cannot sign in",
            "body": "The login code never arrives.",
        })
        messages = response.json()["data"]["messages"]
        self.assertEqual(
            [m["messageType"] for m in messages], ["user_message", "system"]
        )

    def test_a_body_over_two_thousand_characters_is_refused(self):
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "Long one",
            "body": "x" * 2001,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_category_outside_the_three_public_ones_is_refused(self):
        response = self.client.post(LIST_URL, {
            "category": "safety_screening",
            "subject": "Trying an internal category",
            "body": "Should not be accepted.",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signing_out_makes_the_endpoint_unavailable(self):
        self.client.logout()
        self.assertIn(
            self.client.get(LIST_URL).status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class TicketAttachmentUploadTests(UserTicketAPITestCase):
    def submit_with(self, upload):
        return self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "With an attachment",
            "body": "See attached.",
            "files": upload,
        }, format="multipart")

    def test_a_pdf_is_accepted_and_recorded_against_the_first_message(self):
        response = self.submit_with(pdf())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        messages = response.json()["data"]["messages"]
        attachments = messages[0]["attachments"]
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["filename"], "report.pdf")

    def test_an_executable_is_refused(self):
        response = self.submit_with(
            SimpleUploadedFile("payload.exe", b"MZ" + b"0" * 64, content_type="application/pdf")
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_file_over_ten_megabytes_is_refused(self):
        oversized = SimpleUploadedFile(
            "huge.pdf", b"0" * (11 * 1024 * 1024), content_type="application/pdf"
        )
        self.assertEqual(self.submit_with(oversized).status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_refused_upload_leaves_no_ticket_behind(self):
        before = Ticket.objects.count()
        self.submit_with(SimpleUploadedFile("payload.exe", b"MZ", content_type="application/pdf"))
        self.assertEqual(Ticket.objects.count(), before)


class TicketListTests(UserTicketAPITestCase):
    def test_the_list_holds_only_my_own_tickets(self):
        mine = self.make_ticket(subject="Mine")
        self.make_ticket(owner=self.stranger, subject="Not mine")

        items = self.client.get(LIST_URL).json()["data"]["items"]
        self.assertEqual([row["id"] for row in items], [mine.pk])

    def test_the_envelope_carries_all_five_pagination_keys(self):
        self.make_ticket()
        data = self.client.get(LIST_URL).json()["data"]
        self.assertEqual(
            set(data), {"items", "total", "page", "limit", "hasMore"}
        )

    def test_asking_for_more_than_a_hundred_gets_a_hundred_not_an_error(self):
        self.make_ticket()
        response = self.client.get(LIST_URL, {"limit": 200})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["limit"], 100)

    def test_a_nonsense_limit_falls_back_to_the_default(self):
        self.make_ticket()
        response = self.client.get(LIST_URL, {"limit": "banana"})
        self.assertEqual(response.json()["data"]["limit"], 10)

    def test_has_more_is_true_only_while_pages_remain(self):
        for n in range(3):
            self.make_ticket(subject=f"Ticket {n}")
        first = self.client.get(LIST_URL, {"limit": 2, "page": 1}).json()["data"]
        second = self.client.get(LIST_URL, {"limit": 2, "page": 2}).json()["data"]
        self.assertTrue(first["hasMore"])
        self.assertFalse(second["hasMore"])

    def test_the_most_recently_updated_ticket_comes_first(self):
        older = self.make_ticket(subject="Older")
        self.make_ticket(subject="Newer")
        lifecycle.add_user_reply(ticket=older, user=self.requester, body="Any update?")

        items = self.client.get(LIST_URL).json()["data"]["items"]
        self.assertEqual(items[0]["id"], older.pk)


class TicketDetailTests(UserTicketAPITestCase):
    def test_someone_elses_ticket_is_reported_as_missing_not_forbidden(self):
        theirs = self.make_ticket(owner=self.stranger)
        response = self.client.get(f"{LIST_URL}{theirs.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_ticket_that_does_not_exist_is_also_a_404(self):
        self.assertEqual(
            self.client.get(f"{LIST_URL}999999/").status_code, status.HTTP_404_NOT_FOUND
        )

    def test_internal_notes_never_appear_in_the_response_body(self):
        ticket = self.make_ticket()
        lifecycle.add_internal_note(
            ticket=ticket, actor=self.agent, body="Escalating, do not tell the student.",
        )
        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Looking into it.")

        payload = self.client.get(f"{LIST_URL}{ticket.pk}/").json()["data"]
        types = [m["messageType"] for m in payload["messages"]]
        self.assertNotIn(TicketMessageType.INTERNAL_NOTE, types)
        self.assertNotIn("do not tell the student", self.client.get(
            f"{LIST_URL}{ticket.pk}/"
        ).content.decode())

    def test_a_soft_deleted_message_is_not_rendered(self):
        from django.utils import timezone

        ticket = self.make_ticket()
        first = ticket.messages.first()
        first.deleted_at = timezone.now()
        first.save(update_fields=["deleted_at"])

        payload = self.client.get(f"{LIST_URL}{ticket.pk}/").json()["data"]
        self.assertNotIn(first.pk, [m["id"] for m in payload["messages"]])

    def test_a_support_reply_is_attributed_to_support_not_to_a_named_person(self):
        ticket = self.make_ticket()
        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Looking into it.")

        payload = self.client.get(f"{LIST_URL}{ticket.pk}/").json()["data"]
        reply = [m for m in payload["messages"] if m["messageType"] == "support_reply"][0]
        self.assertEqual(reply["author"], "Support")

    def test_the_detail_body_exposes_no_priority_and_no_assignee(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        payload = self.client.get(f"{LIST_URL}{ticket.pk}/").json()["data"]
        self.assertNotIn("priority", payload)
        self.assertNotIn("assignee", payload)


class TicketReplyTests(UserTicketAPITestCase):
    def test_replying_adds_my_message_to_the_timeline(self):
        ticket = self.make_ticket()
        response = self.client.post(
            f"{LIST_URL}{ticket.pk}/messages/", {"body": "Still stuck."}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        bodies = [m["body"] for m in response.json()["data"]["messages"]]
        self.assertIn("Still stuck.", bodies)

    def test_replying_to_a_resolved_ticket_reopens_it(self):
        ticket = self.make_ticket()
        lifecycle.resolve(ticket=ticket, actor=self.agent)

        response = self.client.post(
            f"{LIST_URL}{ticket.pk}/messages/", {"body": "This is still broken."}
        )
        self.assertEqual(response.json()["data"]["status"], "open")

    def test_writing_to_someone_elses_ticket_is_a_404_like_reading_it(self):
        theirs = self.make_ticket(owner=self.stranger)
        response = self.client.post(
            f"{LIST_URL}{theirs.pk}/messages/", {"body": "Let me in."}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TicketAttachmentDownloadTests(UserTicketAPITestCase):
    def attachment_url(self, ticket, attachment_id):
        return f"{LIST_URL}{ticket.pk}/attachments/{attachment_id}/"

    def test_i_can_download_the_file_i_attached(self):
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "With an attachment",
            "body": "See attached.",
            "files": pdf(),
        }, format="multipart")
        data = response.json()["data"]
        attachment_id = data["messages"][0]["attachments"][0]["id"]

        ticket = Ticket.objects.get(pk=data["id"])
        download = self.client.get(self.attachment_url(ticket, attachment_id))
        self.assertIn(download.status_code, (status.HTTP_200_OK, status.HTTP_302_FOUND))

    def test_a_file_attached_to_an_internal_note_is_invisible_to_me(self):
        ticket = self.make_ticket()
        from apps.tickets.services.attachments import stored_attachments

        with stored_attachments([pdf("internal.pdf")]) as rows:
            note = lifecycle.add_internal_note(
                ticket=ticket, actor=self.agent, body="Internal only.", attachments=rows
            )
        attachment_id = note.attachments.get().pk

        response = self.client.get(self.attachment_url(ticket, attachment_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_an_attachment_on_someone_elses_ticket_is_invisible_to_me(self):
        from apps.tickets.services.attachments import stored_attachments

        theirs = self.make_ticket(owner=self.stranger)
        with stored_attachments([pdf("theirs.pdf")]) as rows:
            message = lifecycle.add_support_reply(
                ticket=theirs, actor=self.agent, body="Here you go.", attachments=rows
            )
        attachment_id = message.attachments.get().pk

        response = self.client.get(self.attachment_url(theirs, attachment_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
