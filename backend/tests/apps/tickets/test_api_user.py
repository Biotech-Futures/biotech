import tempfile
from pathlib import Path

from unittest import skipIf
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from django.core.cache import cache
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
from apps.tickets.serializers import PUBLIC_TICKET_CATEGORIES
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
        # Submission is rate-limited per user, and the throttle counter lives
        # in the cache, which outlives the per-test transaction rollback that
        # recycles user ids. Clear it so test order cannot make one of these
        # fail. Safe here only because settings_test pins CACHES to locmem.
        cache.clear()
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
            category=TicketCategory.HELP_STUDENT_GROUP,
            subject=subject,
            body="I get an error opening my group.",
        )


class RequesterEndpointPermissionTests(UserTicketAPITestCase):
    """No requester route answers an anonymous caller.

    ⚠️ Measured, so that nobody credits this with more than it does:

    * Deleting ``permission_classes`` from these views — survives. The project
      default is already ``IsAuthenticated``, so nothing changes. Two findings
      that claimed otherwise were correctly thrown out for this reason.
    * Changing them to ``[AllowAny]`` — caught, all five rows.
    * Flipping the project default to ``AllowAny`` — survives, because an
      explicit ``permission_classes`` on the view wins over it. That default is
      pinned separately below; no ticket view inherits from it.

    So this is a guard against a view being opened on purpose, and against the
    refusal arriving as a crash rather than a 403 — the detail route reaches
    for ``request.user`` and 500s on AnonymousUser if it is ever reached
    ungated. It is not a guard against the line going missing.
    """

    def test_no_requester_route_answers_an_anonymous_caller(self):
        ticket = self.make_ticket()
        self.client.logout()
        operations = [
            ("GET list", lambda: self.client.get("/api/v1/tickets/")),
            ("POST create", lambda: self.client.post(
                "/api/v1/tickets/",
                {"category": TicketCategory.HELP_STUDENT_GROUP,
                 "subject": "Hello", "body": "Something is wrong."},
                format="json")),
            ("GET detail", lambda: self.client.get(f"/api/v1/tickets/{ticket.pk}/")),
            ("POST reply", lambda: self.client.post(
                f"/api/v1/tickets/{ticket.pk}/messages/",
                {"body": "Any news?"}, format="json")),
            ("GET attachment", lambda: self.client.get(
                f"/api/v1/tickets/{ticket.pk}/attachments/1/")),
        ]
        for label, call in operations:
            with self.subTest(operation=label):
                self.assertEqual(
                    call().status_code, status.HTTP_403_FORBIDDEN,
                    f"{label} answered a caller with no session",
                )

    def test_the_project_wide_default_permission_is_authenticated(self):
        """A configuration assertion, and deliberately not a behavioural one.

        Nothing in the ticketing app inherits this default: every view sets
        ``permission_classes`` explicitly, so flipping it here changes none of
        their responses and no request-level test can see it. It is still the
        backstop for any view added without that line, which is the ordinary
        way a new endpoint gets written, so it is worth one direct assertion
        on the setting rather than none at all.
        """
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.settings import api_settings

        self.assertEqual(
            list(api_settings.DEFAULT_PERMISSION_CLASSES), [IsAuthenticated],
            "a view added without permission_classes would now be open",
        )


@skipIf(
    connection.vendor == "sqlite",
    "Tied-row order is stable on SQLite, so this would pass without testing "
    "anything. Runs against local Postgres (--settings=config.settings_local).",
)
class RequesterListOrderingIsTotalTests(UserTicketAPITestCase):
    """"My enquiries" pages over a live sort key, exactly like the queue.

    The queue's half of this was fixed and pinned; this half was fixed and not
    pinned, so ``-pk`` could be taken back out of views.py with the whole
    suite green. A requester who submits several enquiries in one sitting is
    the ordinary way rows end up sharing ``updated_at``, and Show more pages
    with OFFSET over the same ordering.
    """

    def test_paging_through_tied_tickets_shows_each_one_exactly_once(self):
        stamp = timezone.now()
        Ticket.objects.bulk_create([
            Ticket(
                ticket_number=f"SUP-2026-9{i:04d}",
                subject=f"Tied {i}",
                body="x",
                category=TicketCategory.HELP_STUDENT_GROUP,
                created_by=self.requester,
                created_at=stamp,
                updated_at=stamp,
                support_updated_at=stamp,
            )
            for i in range(60)
        ])
        expected = set(
            Ticket.objects.filter(created_by=self.requester)
            .values_list("pk", flat=True)
        )

        seen, page = [], 1
        while True:
            data = self.client.get(
                "/api/v1/tickets/", {"page": page, "limit": 10}
            ).json()["data"]
            seen.extend(row["id"] for row in data["items"])
            if not data["hasMore"]:
                break
            page += 1

        self.assertEqual(len(seen), len(set(seen)), "an enquiry appeared on two pages")
        self.assertEqual(
            set(seen), expected,
            f"{len(expected - set(seen))} enquiries never appeared on any page",
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

    def test_the_requester_may_choose_a_priority(self):
        """The client's answer on 2026-09-04: "the person raising the enquiry
        (not necessarily a student) should be able to set a priority, but the
        support agent should be able to change it"."""
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "Locked out before a deadline",
            "body": "I cannot sign in and my report is due tonight.",
            "priority": "high",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["priority"], "high")
        self.assertEqual(
            Ticket.objects.get(pk=response.data["data"]["id"]).priority, "high"
        )

    def test_every_priority_the_form_offers_is_accepted(self):
        for value in ("high", "normal", "low"):
            with self.subTest(priority=value):
                response = self.client.post(LIST_URL, {
                    "category": TicketCategory.ACCOUNT_ACCESS,
                    "subject": f"Priority {value}",
                    "body": "Please take a look.",
                    "priority": value,
                })
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(response.data["data"]["priority"], value)

    def test_a_submission_without_a_priority_is_normal(self):
        """A form posted without the field keeps working, and "they did not
        say" gets the same answer as "they said Normal" rather than a fourth
        value support would have to interpret."""
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "No priority given",
            "body": "Please take a look.",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["priority"], "normal")

    def test_a_priority_the_model_does_not_know_is_refused(self):
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "Made-up priority",
            "body": "Please take a look.",
            "priority": "critical",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_category_outside_the_public_list_is_refused(self):
        response = self.client.post(LIST_URL, {
            "category": "safety_screening",
            "subject": "Trying an internal category",
            "body": "Should not be accepted.",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_screening_category_is_not_offered_to_requesters(self):
        """flagged_content is a real category and must still be refused here.

        Separate from the test above, which uses a value that exists nowhere.
        This one uses a value the model genuinely accepts, so it fails the
        moment somebody builds PUBLIC_TICKET_CATEGORIES from
        TicketCategory.choices instead of spelling it out.
        """
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.FLAGGED_CONTENT,
            "subject": "Trying the screening category",
            "body": "Should not be accepted.",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_public_categories_are_the_eight_the_client_asked_for(self):
        """The client gave this list on 2026-09-04, in this order.

        Pinned as an exact ordered tuple, values and labels both: the labels
        are what a requester reads, and the order is what the dropdown renders.
        Their capitalisation of "General Question" is theirs, not a slip.

        Also pins the absence of programs_groups, which was ours and which they
        replaced.
        """
        self.assertEqual(
            [(value, TicketCategory(value).label)
             for value in PUBLIC_TICKET_CATEGORIES],
            [
                ("account_access", "Account and access"),
                ("registration", "Registration"),
                ("help_student_group", "Help with a student or group"),
                ("help_mentor", "Help with a mentor"),
                ("technical_issue", "Technical issue"),
                ("certificates_records", "Certificates and records"),
                ("general_question", "General Question"),
                ("other", "Other"),
            ],
        )
        self.assertNotIn(
            TicketCategory.FLAGGED_CONTENT, PUBLIC_TICKET_CATEGORIES
        )
        self.assertNotIn("programs_groups", TicketCategory.values)

    def test_every_public_category_is_actually_accepted(self):
        """Guards the other direction: the list above is not just a string.

        A value could be listed in PUBLIC_TICKET_CATEGORIES and still be
        rejected by the model's choices, and the pin above would not notice.
        """
        for category in PUBLIC_TICKET_CATEGORIES:
            with self.subTest(category=category):
                response = self.client.post(LIST_URL, {
                    "category": category,
                    "subject": f"About {category}",
                    "body": "Please take a look.",
                })
                self.assertEqual(
                    response.status_code, status.HTTP_201_CREATED,
                    msg=f"{category} is offered but not accepted",
                )

    def test_signing_out_makes_the_endpoint_unavailable(self):
        """403 exactly. The pair this used to accept could not fail on any
        mutation of the gate, and 401 is not reachable here: DRF answers it
        only when an authentication class offers a WWW-Authenticate header,
        and SessionAuthentication is the only one this project configures.
        """
        self.client.logout()

        response = self.client.get(LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("WWW-Authenticate", response.headers)


class TicketAttachmentUploadTests(UserTicketAPITestCase):
    def submit_with(self, upload):
        return self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "With an attachment",
            "body": "See attached.",
            "files": upload,
        }, format="multipart")

    def test_six_attachments_are_refused_by_the_backend(self):
        """The cap the frontend constant claims to agree with.

        supportAPI.spec.ts asserts its own MAX_ATTACHMENTS is 5, which proves
        nothing about this side. This is the assertion that makes the two
        agree, and it is the only test of the cap that exists.
        """
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "Six files",
            "body": "See attached.",
            "files": [pdf(f"page{n}.pdf") for n in range(6)],
        }, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_five_attachments_are_accepted(self):
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.ACCOUNT_ACCESS,
            "subject": "Five files",
            "body": "See attached.",
            "files": [pdf(f"page{n}.pdf") for n in range(5)],
        }, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            len(response.json()["data"]["messages"][0]["attachments"]), 5
        )

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

    def test_the_envelope_carries_the_pagination_keys_and_the_walk(self):
        """Exact-set, so a key cannot be added or dropped unnoticed.

        "asOf" and "after" are the two halves of one thing, and neither works
        without the other: the snapshot fixes which enquiries are in this walk
        and in what order, the cursor fixes where the reader has got to. Send
        the snapshot alone and it is ignored; send the cursor alone and it is
        refused. "Show more" carries both, and that is what stops an enquiry
        that gets a reply mid-walk from landing on no page at all.
        """
        self.make_ticket()
        data = self.client.get(LIST_URL).json()["data"]
        self.assertEqual(
            set(data),
            {"items", "total", "page", "limit", "hasMore", "asOf", "after"},
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

    def test_submitting_is_rate_limited_but_reading_is_not(self):
        """Both halves matter.

        The cap exists because each submission puts an email on the same
        four-worker pool as login codes, so one looping account can delay
        everybody's sign-in. But a person waiting for an answer refreshes
        their own list constantly, and throttling that would punish exactly
        the behaviour the feature is for.
        """
        # Patched on the class, not through override_settings: DRF copies
        # DEFAULT_THROTTLE_RATES onto SimpleRateThrottle at import time, so
        # changing the setting afterwards has no effect on an already-imported
        # throttle.
        from unittest.mock import patch

        from apps.tickets.views import WriteOnlyScopedThrottle

        with patch.object(
            WriteOnlyScopedThrottle, "THROTTLE_RATES", {"ticket_create": "2/hour"}
        ):
            cache.clear()
            payload = {
                "category": TicketCategory.ACCOUNT_ACCESS,
                "subject": "Throttle probe",
                "body": "x",
            }
            first = self.client.post(LIST_URL, payload)
            second = self.client.post(LIST_URL, payload)
            third = self.client.post(LIST_URL, payload)

            self.assertEqual(first.status_code, status.HTTP_201_CREATED)
            self.assertEqual(second.status_code, status.HTTP_201_CREATED)
            self.assertEqual(third.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

            # Reading is exempt: still fine after the write cap is spent.
            self.assertEqual(
                self.client.get(LIST_URL).status_code, status.HTTP_200_OK
            )
        cache.clear()

    def test_an_absurd_page_number_cannot_overflow_the_offset(self):
        """Postgres computes OFFSET as a bigint and raises when it overflows.

        Asserted on the helper rather than through the API, because the test
        database is SQLite and SQLite accepts an OFFSET of 10**18 without
        complaint — an HTTP-level assertion here would pass while production
        returned a 500.
        """
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from apps.tickets.views import _page_params

        request = Request(
            APIRequestFactory().get(LIST_URL, {"page": 10 ** 18, "limit": 100})
        )
        page, limit = _page_params(request)
        self.assertLess((page - 1) * limit, 2 ** 63 - 1)

    def test_a_page_past_the_end_is_an_empty_page_not_an_error(self):
        self.make_ticket()
        data = self.client.get(LIST_URL, {"page": 10 ** 18}).json()["data"]
        self.assertEqual(data["items"], [])
        self.assertFalse(data["hasMore"])

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

    def test_a_bounced_resolution_email_is_not_shown_to_the_requester(self):
        """The bounce notice names the requester's own address.

        It is written for an agent — "could not be delivered, please follow
        up" — and it used to be a SYSTEM message, which the requester's view
        does show. So the person whose email had just failed read a note
        about themselves, addressed to somebody else, on their own page.

        Asserted through the endpoint rather than on the message type,
        because the type is only a proxy: what matters is that the sentence
        and the address do not come back in this response.
        """
        from apps.tickets.services import emails

        ticket = self.make_ticket()
        emails._record_delivery_failure(ticket.pk, self.requester.email)(
            RuntimeError("relay refused")
        )

        body = self.client.get(f"{LIST_URL}{ticket.pk}/").content.decode()
        self.assertNotIn("could not be delivered", body)
        self.assertNotIn(self.requester.email, body)

    def test_a_soft_deleted_message_is_not_rendered(self):
        from django.utils import timezone

        ticket = self.make_ticket()
        first = ticket.messages.first()
        first.deleted_at = timezone.now()
        first.save(update_fields=["deleted_at"])

        payload = self.client.get(f"{LIST_URL}{ticket.pk}/").json()["data"]
        self.assertNotIn(first.pk, [m["id"] for m in payload["messages"]])

    def test_the_body_of_a_support_reply_reaches_the_requester(self):
        """The forward half of the internal-note wall.

        The suite was thorough about what must NOT reach the requester and
        silent about what must. A filter written as an allow-list instead of
        a deny-list keeps internal notes hidden and drops support replies with
        it, and every existing test stayed green through exactly that mutation.
        This is the platform answering a child who asked for help, so it gets
        an assertion of its own.
        """
        ticket = self.make_ticket()
        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent, body="Try resetting from the login page.",
        )

        payload = self.client.get(f"{LIST_URL}{ticket.pk}/").json()["data"]
        replies = [m for m in payload["messages"] if m["messageType"] == "support_reply"]
        self.assertEqual(len(replies), 1, "the support reply never reached the requester")
        self.assertEqual(replies[0]["body"], "Try resetting from the login page.")

    def test_a_support_reply_is_attributed_to_support_not_to_a_named_person(self):
        ticket = self.make_ticket()
        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Looking into it.")

        payload = self.client.get(f"{LIST_URL}{ticket.pk}/").json()["data"]
        reply = [m for m in payload["messages"] if m["messageType"] == "support_reply"][0]
        self.assertEqual(reply["author"], "Support")

    def test_the_detail_body_never_names_the_agent_working_the_ticket(self):
        """DEC-017. The requesters are minors; who is handling their ticket is
        not information they are given, and "Support" is what the timeline
        already shows for the same reason."""
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        payload = self.client.get(f"{LIST_URL}{ticket.pk}/").json()["data"]
        self.assertNotIn("assignee", payload)
        self.assertNotIn("Sam", str(payload))

    def test_the_detail_body_shows_the_priority_they_chose(self):
        """Changed 2026-09-04: the requester sets the priority, so hiding it
        back from them would mean they could not tell whether their choice
        registered."""
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(priority="high")
        payload = self.client.get(f"{LIST_URL}{ticket.pk}/").json()["data"]
        self.assertEqual(payload["priority"], "high")

    def test_the_list_row_shows_the_priority_too(self):
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(priority="low")
        rows = self.client.get(LIST_URL).json()["data"]["items"]
        row = [r for r in rows if r["id"] == ticket.pk][0]
        self.assertEqual(row["priority"], "low")


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


class TheTwoClocksAreVisibleToTheRequesterTests(UserTicketAPITestCase):
    """The requester's clock must never carry support activity.

    This is the privacy mechanism the whole "two clocks" design exists for: an
    internal note is work the requester is not party to, so it must not make
    their ticket look like it has news. If it does, they open a ticket that
    says it changed and find nothing changed — and repeatedly, because agents
    write notes far more often than replies.

    The support side of this wall had a test. The requester side, which is the
    side the promise is made to, had none: swapping ``updated_at`` for
    ``support_updated_at`` in the serialiser and in the ordering left the whole
    suite green.
    """

    def test_an_internal_note_does_not_touch_the_requesters_last_updated(self):
        ticket = self.make_ticket()
        before = self.client.get(LIST_URL).json()["data"]["items"][0]["lastUpdated"]

        lifecycle.add_internal_note(
            ticket=ticket, actor=self.agent, body="Escalating internally."
        )

        after = self.client.get(LIST_URL).json()["data"]["items"][0]["lastUpdated"]
        self.assertEqual(after, before, "an internal note moved the requester's clock")

        # And prove the note really did happen, so this cannot pass by the
        # note silently failing to be written.
        ticket.refresh_from_db()
        self.assertGreater(ticket.support_updated_at, ticket.updated_at)

    def test_a_support_reply_does_touch_it(self):
        """The other half: the clock has to move for things they can see."""
        ticket = self.make_ticket()
        before = self.client.get(LIST_URL).json()["data"]["items"][0]["lastUpdated"]

        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent, body="Here is what we found."
        )

        after = self.client.get(LIST_URL).json()["data"]["items"][0]["lastUpdated"]
        self.assertGreater(after, before, "a real reply left the ticket looking stale")

    def test_the_requesters_list_is_not_ordered_by_support_activity(self):
        older = self.make_ticket(subject="Older")
        self.make_ticket(subject="Newer")

        # Support activity on the older one. It must not float for them.
        lifecycle.add_internal_note(
            ticket=older, actor=self.agent, body="Looking at this one."
        )

        subjects = [r["subject"] for r in self.client.get(LIST_URL).json()["data"]["items"]]
        self.assertEqual(
            subjects[0], "Newer",
            "an internal note reordered the requester's own list",
        )


class RequesterAttachmentAccessTests(UserTicketAPITestCase):
    """The download lookup's conditions, one mutation each.

    Five conditions guard this view and three of them could be deleted with
    the suite still green. They are not interchangeable: two are about
    reaching somebody else's file, and one is about a file on a ticket that no
    longer exists.
    """

    def setUp(self):
        super().setUp()
        self.ticket = self.make_ticket()
        data = self.client.post(
            LIST_URL,
            {"category": TicketCategory.HELP_STUDENT_GROUP, "subject": "With a file",
             "body": "See attached.", "files": pdf()},
            format="multipart",
        ).json()["data"]
        self.with_file = Ticket.objects.get(pk=data["id"])
        self.attachment_id = data["messages"][0]["attachments"][0]["id"]

    def url(self, ticket):
        return f"{LIST_URL}{ticket.pk}/attachments/{self.attachment_id}/"

    def test_the_owner_can_download_their_own_attachment(self):
        response = self.client.get(self.url(self.with_file))
        # 302 when a real blob store is configured, 200 when streaming locally.
        self.assertIn(
            response.status_code, (status.HTTP_200_OK, status.HTTP_302_FOUND)
        )

    def test_an_attachment_cannot_be_fetched_through_another_ticket(self):
        # The ticket_id in the path has to match the one the attachment hangs
        # on. Without that condition any id the requester owns opens any
        # attachment id in the table.
        response = self.client.get(self.url(self.ticket))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_stranger_cannot_download_it(self):
        self.client.force_login(self.stranger)
        response = self.client.get(self.url(self.with_file))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_an_attachment_on_a_deleted_ticket_is_gone(self):
        Ticket.objects.filter(pk=self.with_file.pk).update(deleted_at=timezone.now())
        response = self.client.get(self.url(self.with_file))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_an_attachment_on_a_deleted_message_is_gone(self):
        self.with_file.messages.update(deleted_at=timezone.now())
        response = self.client.get(self.url(self.with_file))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AttachmentPipelineTests(UserTicketAPITestCase):
    """The upload pipeline's own promises: order, cleanup, and the whitelist.

    All three held when checked by hand and none had a test, which for a
    pipeline that writes to storage before the database is the difference
    between "no litter" and "litter nobody will ever find".
    """

    def stored_files(self):
        """Every file currently in this test run's media root."""
        media = Path(settings.MEDIA_ROOT)
        if not media.exists():
            return set()
        return {p for p in media.rglob("*") if p.is_file()}

    def test_a_failed_insert_removes_the_blobs_it_uploaded(self):
        # The upload finishes before the transaction opens, so a failed
        # insert has already written to storage — the context manager's whole
        # job is to take that back out.
        before = self.stored_files()
        with patch(
            "apps.tickets.views.lifecycle.create_ticket",
            side_effect=RuntimeError("insert failed after upload"),
        ):
            # The platform's exception handler turns this into a 500 response
            # rather than letting it propagate; either way the insert failed.
            response = self.client.post(LIST_URL, {
                "category": TicketCategory.HELP_STUDENT_GROUP,
                "subject": "Doomed", "body": "See attached.",
                "files": pdf(),
            }, format="multipart")
        self.assertEqual(response.status_code, 500)

        self.assertEqual(
            self.stored_files(), before,
            "a blob outlived the insert that failed — orphaned litter",
        )

    def test_a_rejected_batch_is_never_uploaded_at_all(self):
        # Validation must run before the first byte reaches storage. Running
        # it after would still end clean (the ExitStack removes the blobs),
        # so the end state cannot tell the two orders apart — whether an
        # upload HAPPENED can.
        from apps.tickets.services import attachments as attachments_module

        with patch.object(
            attachments_module.ticket_files, "stored_file"
        ) as stored:
            response = self.client.post(LIST_URL, {
                "category": TicketCategory.HELP_STUDENT_GROUP,
                "subject": "Six files", "body": "Too many.",
                "files": [pdf(f"f{i}.pdf") for i in range(6)],
            }, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        stored.assert_not_called()

    def test_the_extension_whitelist_rejects_on_its_own(self):
        # PDF content, PDF content type, executable file name: every other
        # check passes and the whitelist is the only thing standing. The
        # suite's existing "rejects an executable" test uses real executable
        # bytes, which the magic-number guard catches first — so the
        # whitelist could gain "exe" without anything going red.
        response = self.client.post(LIST_URL, {
            "category": TicketCategory.HELP_STUDENT_GROUP,
            "subject": "Disguised", "body": "See attached.",
            "files": SimpleUploadedFile(
                "evil.exe", b"%PDF-1.4" + b"0" * 128,
                content_type="application/pdf",
            ),
        }, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Ticket.objects.count(), 0)


class RequesterErrorTranslationTests(UserTicketAPITestCase):
    """The requester-side twins of translations only the admin side had."""

    def test_a_reply_hitting_a_just_deleted_ticket_is_a_404_not_a_crash(self):
        # The admin side pinned this translation for its four write actions;
        # the requester's reply path had no equivalent, so dropping its
        # except-clause turned a mid-request delete into a 500 in the
        # requester's face — while they were being told "reply to reopen".
        ticket = self.make_ticket()
        with patch(
            "apps.tickets.views.lifecycle.add_user_reply",
            side_effect=lifecycle.TicketGone("deleted under us"),
        ):
            response = self.client.post(
                f"{LIST_URL}{ticket.pk}/messages/", {"body": "Still stuck."},
            )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_page_zero_is_treated_as_the_first_page(self):
        # Without the lower-bound guard, page=0 becomes OFFSET -10, which
        # Django refuses with an exception — a 500 for typing a zero into
        # the address bar.
        self.make_ticket()
        response = self.client.get(LIST_URL, {"page": "0"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["page"], 1)


class ReplyingIsRateLimitedTests(UserTicketAPITestCase):
    """The cap the reply endpoint did not have.

    Submitting a ticket has been capped since it was written, and the reason
    given for it applies here too: the same stored_attachments, the same blobs,
    the same place. Forty-five replies in a row all answered 201.

    The rate is patched down rather than exercised at its real value. Sixty
    requests inside one test would be sixty inserts to prove an arithmetic
    comparison, and the thing worth pinning is that the endpoint counts at
    all.
    """

    def reply(self, ticket):
        return self.client.post(
            f"{LIST_URL}{ticket.pk}/messages/", {"body": "Still stuck."}
        )

    def test_a_loop_of_replies_is_stopped(self):
        from unittest.mock import patch

        from apps.tickets.views import MessageWriteThrottle

        ticket = self.make_ticket()
        with patch.object(MessageWriteThrottle, "rate", "2/hour"):
            cache.clear()
            codes = [self.reply(ticket).status_code for _ in range(3)]

        self.assertEqual(
            codes,
            [
                status.HTTP_201_CREATED,
                status.HTTP_201_CREATED,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )

    def test_reading_the_ticket_is_not_touched_by_the_reply_cap(self):
        """Somebody who has just been told to slow down still has to be able
        to read the answer they are waiting for."""
        from unittest.mock import patch

        from apps.tickets.views import MessageWriteThrottle

        ticket = self.make_ticket()
        with patch.object(MessageWriteThrottle, "rate", "1/hour"):
            cache.clear()
            self.reply(ticket)
            self.assertEqual(
                self.reply(ticket).status_code, status.HTTP_429_TOO_MANY_REQUESTS
            )

            self.assertEqual(
                self.client.get(f"{LIST_URL}{ticket.pk}/").status_code,
                status.HTTP_200_OK,
            )

    def test_the_cap_is_per_person_not_shared_across_everybody(self):
        """A shared counter would let one looping account lock every requester
        on the platform out of answering their own ticket."""
        from unittest.mock import patch

        from apps.tickets.views import MessageWriteThrottle

        mine = self.make_ticket()
        theirs = self.make_ticket(owner=self.stranger)
        with patch.object(MessageWriteThrottle, "rate", "1/hour"):
            cache.clear()
            self.reply(mine)
            self.assertEqual(
                self.reply(mine).status_code, status.HTTP_429_TOO_MANY_REQUESTS
            )

            self.client.force_login(self.stranger)
            self.assertEqual(
                self.reply(theirs).status_code, status.HTTP_201_CREATED
            )


class ImpossibleStampsAreRefusedNotCrashedTests(UserTicketAPITestCase):
    """A stamp that only becomes impossible once it is read as UTC.

    ``0001-01-01T00:00:00+14:00`` and ``9999-12-31T23:59:59-12:00`` are legal
    datetimes with a legal offset. Shifting either to UTC pushes it past the
    end of the calendar, and the thing that shifts it is the database layer,
    far below any handler that could answer 400. Left on, that is an
    OverflowError from the query string, reachable by anyone with a login, on
    the requester's own list as well as the support queue.

    Both halves of the walk are covered on purpose: the snapshot and the
    cursor read the same stamps through the same parser, and closing one
    without the other was how this survived the first pass.
    """

    IMPOSSIBLE = ("0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-12:00")

    def test_an_impossible_snapshot_is_refused(self):
        self.make_ticket()
        for stamp in self.IMPOSSIBLE:
            with self.subTest(stamp=stamp):
                response = self.client.get(
                    LIST_URL, {"asOf": stamp, "after": "1_1"}
                )
                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )

    def test_an_impossible_cursor_is_refused(self):
        self.make_ticket()
        for stamp in self.IMPOSSIBLE:
            with self.subTest(stamp=stamp):
                response = self.client.get(
                    LIST_URL,
                    {"asOf": "2026-01-01T00:00:00Z", "after": f"{stamp}_1"},
                )
                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )

    def test_an_ordinary_offset_still_reads(self):
        """The guard rejects the impossible, not everything with an offset."""
        self.make_ticket()
        response = self.client.get(
            LIST_URL, {"asOf": "2026-09-06T10:00:00+10:00"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
