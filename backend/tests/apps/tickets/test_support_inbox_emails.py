"""The two emails to the support inbox (8 October client meeting).

E4, a new enquiry has come in (C-17: "we'd also want emails to go to our
support inbox to say like there is a new inquiry"), and E5, the morning count
of what is still open (C-18: "a daily digest ... this is the number of
inquiries open"; every day, DEC-051). Both in the designer's M-27 and M-28.
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

from apps.common import email_jobs

from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from apps.tickets.services import emails, lifecycle
from apps.tickets.services.handoff import create_ticket_from_screening

User = get_user_model()

DIGEST = "/api/v1/admin/tickets/digest/send/"


def html_of(message) -> str:
    return message.alternatives[0][0]


def plain(text: str) -> str:
    """The words, without tags, entities folded and whitespace squeezed."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&middot;", "·").replace("&#39;", "'")
    return re.sub(r"\s+", " ", text).strip()


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
            self.assertIn(f'href="{expected}"', tag)
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

    def test_a_ticket_from_message_screening_sends_it_nowhere(self):
        """The client's case was "when someone submits a ticket"."""
        sender = User.objects.create_user(email="mia@example.com", password="pass1234")
        message = SimpleNamespace(
            pk=42, group=SimpleNamespace(pk=7, group_name="Team Photosynthesis"), sender_user=sender
        )
        verdict = SimpleNamespace(flagged=True, layer="rule", category="personal_contact", reason="x")
        with self.captureOnCommitCallbacks(execute=True):
            create_ticket_from_screening(message, verdict, "call me")

        self.assertEqual([m.to for m in mail.outbox], [])


class OpenEnquiriesDigestTests(TestCase):
    # 22:07 UTC on Thursday 8 October is 9:07 on Friday 9 October in Sydney.
    NOW = datetime(2026, 10, 8, 22, 7, tzinfo=dt_timezone.utc)

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
        words = plain(html_of(message))
        return {
            label: int(re.search(rf"{label} [^0-9]*?(\d+)", words).group(1))
            for label in ("Open", "In progress", "Pending user", "Of these, overdue")
        }

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
        self.assertIn("We send this summary every morning while enquiries are open.", words)

    def test_one_enquiry_is_one_enquiry(self):
        self.ticket()
        self.send()
        self.assertEqual(mail.outbox[0].subject, "BIOTech Connect: 1 enquiry is still open")

    def test_nothing_open_sends_nothing(self):
        self.ticket(TicketStatus.RESOLVED)
        self.assertEqual(self.send(), {"sent": False, "open": 0})
        self.assertEqual(mail.outbox, [])

    def test_the_button_opens_the_support_queue(self):
        self.ticket()
        self.send()
        html = html_of(mail.outbox[0])
        expected = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/#/admin/tickets"
        tags = re.findall(r'<(?:a\b[^>]*class="cta-link"|v:roundrect\b)[^>]*>', html)
        self.assertEqual(len(tags), 2)
        for tag in tags:
            self.assertIn(f'href="{expected}"', tag)
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

    def test_it_reads_no_repository_variable(self):
        # main's scheduled jobs call the backend at its fixed address; the
        # repository has no variables to read.
        self.assertEqual(self.step["env"]["BACKEND_URL"], "https://api.biotechfutures.org")
        self.assertNotIn("vars.", yaml.safe_dump(self.workflow))

