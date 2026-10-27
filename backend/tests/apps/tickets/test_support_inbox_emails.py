"""The three emails to the support inbox.

E4, a new enquiry has come in (C-17: "we'd also want emails to go to our
support inbox to say like there is a new inquiry"), and E5, the morning count
of what is still open (C-18: "a daily digest ... this is the number of
inquiries open"), from the 8 October meeting, in the designer's M-27 and M-28.
On 20 October the client added E6 ("Please do cause an email to be triggered
from the AI screening flags as well"), set E5 to "9am Sydney time" and "Daily
everyday (weekends included)", and asked for them on System Emails ("Please
ensure this email is integrated into the Systems email feature").
"""

import json
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from types import SimpleNamespace

import yaml

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.admin.services.system_email import get_email_template
from apps.common import email_jobs
from apps.services.email_registry import get_email_type, unknown_merge_tags
from apps.services.models import SystemEmailLog, SystemEmailSettings, SystemEmailTemplate
from apps.services.system_email import clean_email_body, sender_for

from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from apps.tickets.services import emails, lifecycle
from apps.tickets.services.handoff import create_ticket_from_screening
from tests.email_helpers import delivered_destination

User = get_user_model()

DIGEST = "/api/v1/admin/tickets/digest/send/"

SUPPORT_EMAILS = ("ticket_new_for_support", "ticket_flagged_for_support", "ticket_digest")
REQUESTER_EMAILS = ("ticket_submitted", "ticket_reply", "ticket_resolved")


def html_of(message) -> str:
    return message.alternatives[0][0]


def plain(text: str) -> str:
    """The words, without tags, entities folded and whitespace squeezed."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&middot;", "·").replace("&#39;", "'")
    return re.sub(r"\s+", " ", text).strip()


def digest_rows(message) -> dict:
    """The morning count's four numbers, by the label of their row."""
    words = plain(html_of(message))
    return {
        label: int(re.search(rf"{label} [^0-9]*?(\d+)", words).group(1))
        for label in ("Open", "In progress", "Pending user", "Of these, overdue")
    }


def flagged_message(sender):
    """What the screening pipeline hands create_ticket_from_screening."""
    return SimpleNamespace(
        pk=42, group=SimpleNamespace(pk=7, group_name="Team Photosynthesis"), sender_user=sender
    )


class NewEnquiryEmailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.requester = User.objects.create_user(
            email="stella@example.com", password="pass1234",
            first_name="Stella", last_name="Nguyen",
        )
        mail.outbox = []

    def raise_enquiry(self, **fields):
        self.client.force_login(self.requester)
        payload = {
            "category": TicketCategory.TECHNICAL_ISSUE,
            "subject": "Group workspace shows an error when I open it",
            "body": "Since this morning the workspace says Something went wrong.",
            "priority": TicketPriority.HIGH,
            **fields,
        }
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/tickets/", data=json.dumps(payload), content_type="application/json"
            )
        self.assertEqual(response.status_code, 201, response.content)
        return Ticket.objects.get(pk=response.json()["data"]["id"])

    def inbox_copy(self):
        copies = [m for m in mail.outbox if m.to == [settings.TICKET_SUPPORT_INBOX]]
        self.assertEqual(len(copies), 1, [m.to for m in mail.outbox])
        return copies[0]

    def test_a_new_enquiry_is_mailed_to_the_support_inbox(self):
        ticket = self.raise_enquiry()
        message = self.inbox_copy()

        self.assertEqual(settings.TICKET_SUPPORT_INBOX, "support@biotechfutures.org")
        self.assertEqual(message.from_email, settings.TICKET_FROM_EMAIL)
        self.assertEqual(
            message.subject, f"BIOTech Connect: a new enquiry has come in ({ticket.ticket_number})"
        )

    def test_it_says_who_raised_it_what_it_is_how_urgent_and_that_nobody_has_it(self):
        ticket = self.raise_enquiry()
        message = self.inbox_copy()

        for half in (plain(html_of(message)), plain(message.body)):
            with self.subTest(half=half[:40]):
                self.assertIn("Stella Nguyen", half)
                self.assertIn("Technical issue", half)
                self.assertIn("I cannot continue (High priority)", half)
                self.assertIn(ticket.ticket_number, half)
                self.assertIn("Unassigned", half)
        words = plain(html_of(message))
        self.assertIn("Hi support team,", words)
        self.assertIn("A new enquiry has come in", words)
        self.assertIn("Stella Nguyen raised it in the Support Centre. It is not assigned to anyone yet.", words)
        self.assertIn("This is an automatic message from BIOTech Connect.", words)
        # The requester's sign-off is theirs, not the inbox's.
        self.assertNotIn("The BIOTech Futures support team", words)

    def test_each_urgency_reads_as_the_requester_chose_it(self):
        for priority, words in (
            (TicketPriority.HIGH, "I cannot continue (High priority)"),
            (TicketPriority.NORMAL, "I can keep working (Normal priority)"),
            (TicketPriority.LOW, "It can wait (Low priority)"),
        ):
            with self.subTest(priority=priority):
                mail.outbox = []
                cache.clear()
                self.raise_enquiry(priority=priority, subject=f"About {priority}")
                self.assertIn(words, plain(html_of(self.inbox_copy())))

    def test_the_button_opens_it_in_the_support_queue(self):
        ticket = self.raise_enquiry()
        html = html_of(self.inbox_copy())
        expected = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/#/admin/tickets?ticket={ticket.pk}"

        tags = re.findall(r'<(?:a\b[^>]*class="cta-link"|v:roundrect\b)[^>]*>', html)
        self.assertEqual(len(tags), 2)
        for tag in tags:
            href = re.search(r'href="([^"]+)"', tag).group(1)
            self.assertEqual(delivered_destination(href), expected)
        self.assertIn("Open in the support queue", plain(html))
        self.assertNotIn("/#/support/tickets/", html)

    def test_it_does_not_copy_the_message_into_the_mailbox(self):
        self.raise_enquiry(body="My phone number is 0400 111 222 and my school is Hillview.")
        message = self.inbox_copy()

        for half in (html_of(message), message.body):
            self.assertNotIn("0400 111 222", half)
            self.assertNotIn("Hillview", half)

    @override_settings(TICKET_SUPPORT_INBOX="desk@example.com")
    def test_the_inbox_is_a_setting(self):
        self.raise_enquiry()
        self.assertEqual(
            [m.to for m in mail.outbox], [["stella@example.com"], ["desk@example.com"]]
        )


class FlaggedMessageEmailTests(TestCase):
    """E6. The client, 20 October: "Please do cause an email to be triggered
    from the AI screening flags as well"."""

    def setUp(self):
        self.sender = User.objects.create_user(
            email="mia@example.com", password="pass1234", first_name="Mia", last_name="Tran",
        )
        mail.outbox = []

    def flag(self, text="Call me on 0400 111 222", layer="rule", execute=True):
        verdict = SimpleNamespace(
            flagged=True, layer=layer, category="personal_contact", reason="a phone number"
        )
        with self.captureOnCommitCallbacks(execute=execute) as callbacks:
            ticket = create_ticket_from_screening(flagged_message(self.sender), verdict, text)
        return ticket, callbacks

    def test_a_flag_is_mailed_to_the_support_inbox_and_nowhere_else(self):
        ticket, _ = self.flag()

        self.assertEqual([m.to for m in mail.outbox], [[settings.TICKET_SUPPORT_INBOX]])
        message = mail.outbox[0]
        self.assertEqual(message.from_email, settings.TICKET_FROM_EMAIL)
        self.assertEqual(
            message.subject, f"BIOTech Connect: a chat message was flagged ({ticket.ticket_number})"
        )

    def test_it_says_what_happened_how_urgent_it_is_and_that_nobody_has_it(self):
        ticket, _ = self.flag()
        message = mail.outbox[0]

        for half in (plain(html_of(message)), plain(message.body)):
            with self.subTest(half=half[:40]):
                self.assertIn(ticket.ticket_number, half)
                self.assertIn(
                    "The AI screening flagged a message in a group chat and opened an enquiry "
                    "for it. It is not assigned to anyone yet.",
                    half,
                )
                self.assertIn("Flagged content", half)
                self.assertIn("Team Photosynthesis", half)
        words = plain(html_of(message))
        self.assertIn("A chat message was flagged", words)
        self.assertIn("Category: Flagged content · Priority: Normal", words)
        self.assertIn("Unassigned", words)

    def test_a_flag_from_the_language_model_reads_as_high_priority(self):
        self.flag(layer="llm")
        self.assertIn("Priority: High", plain(html_of(mail.outbox[0])))
        self.assertIn("Priority: High", mail.outbox[0].body)

    def test_it_leaves_out_the_message_and_who_wrote_it(self):
        self.flag(text="My number is 0400 111 222 and I live at 12 Hill St")
        message = mail.outbox[0]

        for half in (html_of(message), message.body):
            for private in ("0400 111 222", "12 Hill St", "Mia Tran", "mia@example.com"):
                self.assertNotIn(private, half)
        self.assertIn("The message itself is not in this email.", plain(html_of(message)))

    def test_the_button_opens_it_in_the_support_queue(self):
        ticket, _ = self.flag()
        html = html_of(mail.outbox[0])
        expected = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/#/admin/tickets?ticket={ticket.pk}"

        tags = re.findall(r'<(?:a\b[^>]*class="cta-link"|v:roundrect\b)[^>]*>', html)
        self.assertEqual(len(tags), 2)
        for tag in tags:
            href = re.search(r'href="([^"]+)"', tag).group(1)
            self.assertEqual(delivered_destination(href), expected)
        self.assertIn("Open in the support queue", plain(html))

    def test_it_waits_for_the_screening_batch_to_commit(self):
        # A batch that rolls back must not have mailed anyone.
        _, callbacks = self.flag(execute=False)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()
        self.assertEqual(len(mail.outbox), 1)

    def test_it_is_not_the_new_enquiry_email(self):
        # E4 is for an enquiry someone raised; a flag has nobody behind it.
        self.flag()
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("a new enquiry has come in", mail.outbox[0].subject)


class OpenEnquiriesDigestTests(TestCase):
    # 22:00 UTC on Thursday 8 October is 9am on Friday 9 October in Sydney,
    # when the schedule calls it.
    NOW = datetime(2026, 10, 8, 22, 0, tzinfo=dt_timezone.utc)

    def setUp(self):
        self.requester = User.objects.create_user(
            email="stella@example.com", password="pass1234", first_name="Stella",
        )
        self.agent = User.objects.create_user(email="sam@example.com", password="pass1234")
        SupportScope.objects.create(user=self.agent)
        mail.outbox = []

    def ticket(self, status=TicketStatus.OPEN, **fields):
        with self.captureOnCommitCallbacks(execute=True):
            ticket = lifecycle.create_ticket(
                user=self.requester, category=TicketCategory.OTHER,
                subject=f"A {status} one", body="b",
            )
        if status != TicketStatus.OPEN:
            lifecycle.set_status(ticket=ticket, new_status=status, actor=self.agent)
        if fields:
            Ticket.objects.filter(pk=ticket.pk).update(**fields)
        return ticket

    def send(self):
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            return emails.send_open_tickets_digest(now=self.NOW)

    def rows(self, message):
        return digest_rows(message)

    def test_it_counts_what_is_still_open_and_how_much_of_it_is_overdue(self):
        self.ticket()
        self.ticket(awaiting_support_since=self.NOW - timedelta(days=3))
        self.ticket(TicketStatus.IN_PROGRESS)
        self.ticket(TicketStatus.PENDING_USER)
        self.ticket(TicketStatus.RESOLVED)
        self.ticket(deleted_at=self.NOW)

        result = self.send()

        self.assertEqual(result, {"sent": True, "open": 4, "overdue": 1})
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [settings.TICKET_SUPPORT_INBOX])
        self.assertEqual(message.subject, "BIOTech Connect: 4 enquiries are still open")
        self.assertEqual(
            self.rows(message), {"Open": 2, "In progress": 1, "Pending user": 1, "Of these, overdue": 1}
        )
        self.assertIn("Of these, overdue: 1", message.body)

    def test_it_dates_itself_in_sydney(self):
        self.ticket()
        self.send()
        words = plain(html_of(mail.outbox[0]))
        self.assertIn("Here is where the support queue stands this morning, Friday 9 October 2026.", words)
        self.assertIn("We send this summary every morning, weekends included.", words)

    def test_one_enquiry_is_one_enquiry(self):
        self.ticket()
        self.send()
        self.assertEqual(mail.outbox[0].subject, "BIOTech Connect: 1 enquiry is still open")

    def test_nothing_open_still_sends_a_count_of_zero(self):
        # Jinqi, 21 October: "没有也要发"; the client's "Daily everyday".
        self.ticket(TicketStatus.RESOLVED)

        self.assertEqual(self.send(), {"sent": True, "open": 0, "overdue": 0})
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "BIOTech Connect: No enquiries are open")
        self.assertEqual(
            self.rows(message), {"Open": 0, "In progress": 0, "Pending user": 0, "Of these, overdue": 0}
        )
        self.assertIn("Open: 0", message.body)

    def test_its_rows_are_named_as_the_portal_names_the_statuses(self):
        # The template writes the three labels out (it is on System Emails,
        # whose editor cannot keep a loop), so they have to stay the portal's.
        self.assertEqual(
            [TicketStatus.OPEN.label, TicketStatus.IN_PROGRESS.label, TicketStatus.PENDING_USER.label],
            ["Open", "In progress", "Pending user"],
        )

    def test_the_button_opens_the_support_queue(self):
        self.ticket()
        self.send()
        html = html_of(mail.outbox[0])
        expected = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/#/admin/tickets"
        tags = re.findall(r'<(?:a\b[^>]*class="cta-link"|v:roundrect\b)[^>]*>', html)
        self.assertEqual(len(tags), 2)
        for tag in tags:
            href = re.search(r'href="([^"]+)"', tag).group(1)
            self.assertEqual(delivered_destination(href), expected)
        self.assertIn("Open the support queue", plain(html))


@override_settings(EMAIL_JOBS_TOKEN="jobs-secret", RSVP_REMINDER_TOKEN="")
class DigestTriggerTests(TestCase):
    """Started the way the platform's other scheduled emails are: the email
    jobs' shared token in the X-Email-Jobs-Token header (apps.common.email_jobs)."""

    def setUp(self):
        user = User.objects.create_user(email="stella@example.com", password="pass1234")
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.create_ticket(user=user, category=TicketCategory.OTHER, subject="s", body="b")
        mail.outbox = []

    def call(self, token=None, header="HTTP_X_EMAIL_JOBS_TOKEN"):
        headers = {header: token} if token is not None else {}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(DIGEST, **headers)

    def test_the_right_token_sends_the_count(self):
        response = self.call("jobs-secret")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["sent"], True)
        self.assertEqual([m.to for m in mail.outbox], [[settings.TICKET_SUPPORT_INBOX]])

    def test_a_wrong_or_missing_token_sends_nothing(self):
        for token in ("nope", None):
            with self.subTest(token=token):
                response = self.call(token)
                self.assertEqual(response.status_code, 401)
        self.assertEqual(mail.outbox, [])

    def test_the_header_it_used_before_is_refused(self):
        # X-Reminder-Token, from before the trigger joined the shared jobs.
        # The right value in the wrong header must not send.
        response = self.call("jobs-secret", header="HTTP_X_REMINDER_TOKEN")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(mail.outbox, [])

    @override_settings(EMAIL_JOBS_TOKEN="", RSVP_REMINDER_TOKEN="")
    def test_no_token_configured_is_a_closed_door_not_an_open_one(self):
        response = self.call("")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(mail.outbox, [])

    def test_a_signed_in_agent_cannot_send_it_without_the_token(self):
        agent = User.objects.create_user(email="sam@example.com", password="pass1234")
        SupportScope.objects.create(user=agent)
        self.client.force_login(agent)
        self.assertEqual(self.call().status_code, 401)


class DigestWorkflowTests(SimpleTestCase):
    """The schedule and the endpoint have to agree, and nothing in between
    checks it: a workflow reading a setting nobody sets fails every morning
    on GitHub and nowhere else. Its first version read a repository variable
    that main had already stopped using."""

    def setUp(self):
        path = Path(settings.BASE_DIR).parent / ".github" / "workflows" / "ticket-digest.yml"
        self.workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        (self.step,) = self.workflow["jobs"]["dispatch"]["steps"]

    def test_it_calls_the_endpoint_with_the_email_jobs_token(self):
        env = self.step["env"]
        self.assertEqual(env["JOBS_TOKEN"], "${{ secrets.EMAIL_JOBS_TOKEN }}")
        self.assertIn(f'-H "{email_jobs.HEADER}: ${{JOBS_TOKEN}}"', self.step["run"])
        self.assertIn(reverse("tickets_admin:digest-send"), self.step["run"])

    def test_it_runs_at_9am_sydney_time_every_day(self):
        # The client, 20 October: "9am Sydney time", "Daily everyday (weekends
        # included)". Read in Sydney time, so daylight saving cannot move it.
        # PyYAML reads the bare key `on` as True.
        triggers = self.workflow.get("on", self.workflow.get(True))
        self.assertEqual(
            triggers["schedule"], [{"cron": "0 9 * * *", "timezone": "Australia/Sydney"}]
        )

    def test_it_reads_no_repository_variable(self):
        # main's scheduled jobs call the backend at its fixed address; the
        # repository has no variables to read.
        self.assertEqual(self.step["env"]["BACKEND_URL"], "https://api.biotechfutures.org")
        self.assertNotIn("vars.", yaml.safe_dump(self.workflow))


class SupportEmailsOnSystemEmailsTests(TestCase):
    """The client, 20 October: "Please ensure this email is integrated into
    the Systems email feature", for the three to the support inbox; Jinqi,
    22 October, for the three to the requester as well. All six are on it."""

    NOW = OpenEnquiriesDigestTests.NOW

    def setUp(self):
        cache.clear()
        self.requester = User.objects.create_user(
            email="stella@example.com", password="pass1234", first_name="Stella", last_name="Nguyen",
        )
        self.agent = User.objects.create_user(
            email="sam@example.com", password="pass1234", first_name="Sam", last_name="Lee",
        )
        SupportScope.objects.create(user=self.agent)
        mail.outbox = []

    def raise_enquiry(self):
        with self.captureOnCommitCallbacks(execute=True):
            return lifecycle.create_ticket(
                user=self.requester, category=TicketCategory.OTHER,
                subject="My report will not upload", body="b",
            )

    def flag(self):
        verdict = SimpleNamespace(flagged=True, layer="rule", category="personal_contact", reason="x")
        with self.captureOnCommitCallbacks(execute=True):
            return create_ticket_from_screening(flagged_message(self.requester), verdict, "text")

    def digest(self):
        with self.captureOnCommitCallbacks(execute=True):
            return emails.send_open_tickets_digest(now=self.NOW)

    def to_inbox(self):
        return [m for m in mail.outbox if m.to == [settings.TICKET_SUPPORT_INBOX]]

    def sent(self) -> set:
        """Which of the three reached the support inbox, by subject."""
        found = set()
        for message in self.to_inbox():
            if "a new enquiry has come in" in message.subject:
                found.add("ticket_new_for_support")
            elif "a chat message was flagged" in message.subject:
                found.add("ticket_flagged_for_support")
            elif re.search(r"enquir(y is|ies are) (still )?open$", message.subject):
                found.add("ticket_digest")
        return found

    def test_all_three_are_on_it_and_go_from_support(self):
        for key in SUPPORT_EMAILS:
            with self.subTest(key):
                self.assertEqual(get_email_type(key).default_sender, "support")
                self.assertEqual(sender_for(key).from_email, settings.TICKET_FROM_EMAIL)

    def test_switching_one_off_there_stops_that_one_only(self):
        for key in SUPPORT_EMAILS:
            with self.subTest(key):
                SystemEmailTemplate.objects.all().delete()
                SystemEmailTemplate.objects.create(key=key, is_enabled=False)
                mail.outbox = []

                self.raise_enquiry()
                self.flag()
                result = self.digest()

                self.assertEqual(self.sent(), set(SUPPORT_EMAILS) - {key})
                # The requester's acknowledgement has a switch of its own.
                self.assertIn(["stella@example.com"], [m.to for m in mail.outbox])
                if key == "ticket_digest":
                    self.assertEqual(result["sent"], False)
                    self.assertEqual(result["reason"], "switched_off")

    def test_pausing_every_system_email_stops_all_of_them(self):
        switches = SystemEmailSettings.get()
        switches.emails_enabled = False
        switches.save()

        ticket = self.raise_enquiry()
        self.flag()
        self.assertEqual(self.digest()["reason"], "switched_off")
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.resolve(ticket=ticket, actor=self.agent)

        # The requester's three as well as the inbox's: all on System Emails.
        self.assertEqual(mail.outbox, [])

    def test_wording_saved_there_is_what_goes_out(self):
        self.raise_enquiry()
        SystemEmailTemplate.objects.create(
            key="ticket_digest",
            subject="Queue on {{ today }}: {{ open_total }} open",
            body_html="<p>{{ headline }}. Overdue: {{ overdue }}.</p>",
        )
        mail.outbox = []

        self.digest()

        (message,) = self.to_inbox()
        self.assertEqual(message.subject, "Queue on Friday 9 October 2026: 1 open")
        self.assertIn("1 enquiry is still open. Overdue: 0.", plain(html_of(message)))
        self.assertIn("1 enquiry is still open. Overdue: 0.", message.body)

    def test_the_editor_starts_from_every_part_of_each_one(self):
        # Their ticket box and button are includes; the editor has to render
        # them too (apps.admin.services.system_email._render_content_block).
        parts = {
            "ticket_new_for_support": (
                "{{ requester_name }}", "{{ assignment }}", "{{ category }}", "{{ urgency }}",
                "{{ priority }}", "{{ ticket_number }}", "{{ status_pill }}", "{{ assignee }}",
                "{{ ticket_subject }}", "{{ queue_link }}", "Open in the support queue",
            ),
            "ticket_flagged_for_support": (
                "{{ assignment }}", "{{ category }}", "{{ priority }}", "{{ ticket_number }}",
                "{{ status_pill }}", "{{ assignee }}", "{{ ticket_subject }}", "{{ queue_link }}",
                "Open in the support queue", "The message itself is not in this email.",
            ),
            "ticket_digest": (
                "{{ headline }}", "{{ today }}", "{{ open_count }}", "{{ in_progress_count }}",
                "{{ pending_user_count }}", "{{ overdue }}", "{{ queue_link }}",
                "Open the support queue",
            ),
            "ticket_submitted": (
                "{{ greeting_name }}", "{{ expected_reply }}", "{{ ticket_number }}",
                "{{ status_pill }}", "{{ ticket_subject }}", "{{ ticket_link }}", "Open this enquiry",
            ),
            "ticket_reply": (
                "{{ greeting_name }}", "{{ next_step }}", "{{ ticket_number }}", "{{ status_pill }}",
                "{{ ticket_subject }}", "{{ ticket_link }}", "Open this enquiry",
            ),
            "ticket_resolved": (
                "{{ greeting_name }}", "{{ expected_reply }}", "{{ ticket_number }}",
                "{{ status_pill }}", "{{ ticket_subject }}", "{{ ticket_link }}", "Open this enquiry",
            ),
        }
        for key, expected in parts.items():
            with self.subTest(key):
                body = get_email_template(key)["data"]["defaultBody"]
                for part in expected:
                    self.assertIn(part, body)
                self.assertEqual(unknown_merge_tags(key, body), set())

    def test_saved_unchanged_from_the_editor_it_still_says_whether_anyone_has_it(self):
        # Why that sentence arrives finished: an {% if %} in the template is
        # always true in the editor, and the "nobody" wording would be gone.
        body = clean_email_body(get_email_template("ticket_new_for_support")["data"]["defaultBody"])
        SystemEmailTemplate.objects.create(key="ticket_new_for_support", body_html=body)

        ticket = self.raise_enquiry()
        self.assertIn("It is not assigned to anyone yet.", plain(html_of(self.to_inbox()[0])))

        mail.outbox = []
        Ticket.objects.filter(pk=ticket.pk).update(assignee=self.agent)
        emails.send_new_ticket_to_support(ticket)
        self.assertIn("It is assigned to Sam Lee.", plain(html_of(self.to_inbox()[0])))

    def test_the_summary_saved_unchanged_from_the_editor_keeps_its_numbers(self):
        body = clean_email_body(get_email_template("ticket_digest")["data"]["defaultBody"])
        SystemEmailTemplate.objects.create(key="ticket_digest", body_html=body)
        self.raise_enquiry()
        mail.outbox = []

        self.digest()

        (message,) = self.to_inbox()
        self.assertEqual(
            digest_rows(message), {"Open": 1, "In progress": 0, "Pending user": 0, "Of these, overdue": 0}
        )

    def test_each_send_is_noted_in_its_log(self):
        self.raise_enquiry()
        self.flag()
        self.digest()
        for key in SUPPORT_EMAILS:
            with self.subTest(key):
                self.assertIsNotNone(SystemEmailLog.objects.get(key=key).last_sent_at)

    def test_the_footer_names_the_mailbox_it_goes_from(self):
        self.raise_enquiry()
        self.assertIn(
            "BIOTech Futures &lt;support@biotechfutures.org&gt;</a> to your address book", html_of(self.to_inbox()[0])
        )

        SystemEmailTemplate.objects.create(key="ticket_new_for_support", sender="info")
        mail.outbox = []
        self.raise_enquiry()
        (message,) = self.to_inbox()
        self.assertEqual(message.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertIn("BIOTech Futures &lt;info@biotechfutures.org&gt;</a> to your address book", html_of(message))


class RequesterEmailsOnSystemEmailsTests(TestCase):
    """The three to whoever raised the enquiry, on System Emails since Jinqi
    asked on 22 October ("那发给学生的那几封邮件也加进来吧")."""

    def setUp(self):
        cache.clear()
        self.requester = User.objects.create_user(
            email="stella@example.com", password="pass1234", first_name="Stella", last_name="Nguyen",
        )
        self.agent = User.objects.create_user(
            email="sam@example.com", password="pass1234", first_name="Sam", last_name="Lee",
        )
        SupportScope.objects.create(user=self.agent)
        mail.outbox = []

    def raise_enquiry(self):
        with self.captureOnCommitCallbacks(execute=True):
            ticket = lifecycle.create_ticket(
                user=self.requester, category=TicketCategory.OTHER,
                subject="My report will not upload", body="b",
            )
        lifecycle.claim(ticket=ticket, actor=self.agent)
        return ticket

    def reply(self, ticket, status=TicketStatus.IN_PROGRESS):
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply_with_status(
                ticket=ticket, actor=self.agent, body="Could you send the file again?", next_status=status,
            )

    def resolve(self, ticket):
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.resolve(ticket=ticket, actor=self.agent)

    def to_requester(self):
        return [m for m in mail.outbox if m.to == ["stella@example.com"]]

    def save_unchanged(self, key):
        body = clean_email_body(get_email_template(key)["data"]["defaultBody"])
        SystemEmailTemplate.objects.create(key=key, body_html=body)

    def test_all_three_are_on_it_and_go_from_support(self):
        for key in REQUESTER_EMAILS:
            with self.subTest(key):
                self.assertEqual(get_email_type(key).default_sender, "support")
                self.assertEqual(sender_for(key).from_email, settings.TICKET_FROM_EMAIL)

    def test_switching_the_acknowledgement_off_stops_it_and_nothing_else(self):
        SystemEmailTemplate.objects.create(key="ticket_submitted", is_enabled=False)
        self.raise_enquiry()
        self.assertEqual(self.to_requester(), [])
        # The support inbox still hears about it.
        self.assertEqual([m.to for m in mail.outbox], [[settings.TICKET_SUPPORT_INBOX]])

    def test_switching_the_reply_and_resolution_emails_off_stops_them(self):
        ticket = self.raise_enquiry()
        SystemEmailTemplate.objects.create(key="ticket_reply", is_enabled=False)
        SystemEmailTemplate.objects.create(key="ticket_resolved", is_enabled=False)
        self.reply(ticket)
        self.resolve(ticket)
        self.assertEqual(mail.outbox, [])

    def test_wording_saved_there_is_what_goes_out(self):
        SystemEmailTemplate.objects.create(
            key="ticket_submitted",
            subject="Got it: {{ ticket_number }}",
            body_html="<p>Hi {{ greeting_name }}, {{ ticket_number }} is with us.</p>",
        )
        ticket = self.raise_enquiry()
        (message,) = self.to_requester()
        self.assertEqual(message.subject, f"Got it: {ticket.ticket_number}")
        self.assertIn(f"Hi Stella, {ticket.ticket_number} is with us.", plain(html_of(message)))

    def test_saved_unchanged_the_reply_still_says_the_right_next_step(self):
        # Why the next step arrives finished: in the editor the template's
        # branches would all have fallen to one of the three.
        self.save_unchanged("ticket_reply")
        ticket = self.raise_enquiry()

        self.reply(ticket, status=TicketStatus.PENDING_USER)
        self.assertIn("We have asked you for some more information.", plain(html_of(self.to_requester()[0])))

        self.reply(ticket, status=TicketStatus.IN_PROGRESS)
        self.assertIn(
            "Open the enquiry to read it, and reply there if we have asked you for anything.",
            plain(html_of(self.to_requester()[0])),
        )

    def test_saved_unchanged_the_resolution_email_still_shows_resolved_in_grey_with_a_tick(self):
        # Why the pill arrives finished: in the editor it would have been the
        # open pill's green for every status.
        self.save_unchanged("ticket_resolved")
        ticket = self.raise_enquiry()
        self.resolve(ticket)
        html = html_of(self.to_requester()[0])
        self.assertIn("background:#E6E8E9; color:#4F575C;", html)
        self.assertIn("&#10003;", html)
        self.assertNotIn("background:#D3ECE0", html)

