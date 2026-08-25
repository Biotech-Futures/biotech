from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import TestCase, override_settings

from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
    TicketChannel,
    TicketMessageType,
    TicketStatus,
)
from apps.tickets.services import lifecycle

User = get_user_model()


class TicketEmailTestCase(TestCase):
    """Emails go out on transaction commit, which a TestCase never reaches on
    its own — hence captureOnCommitCallbacks around anything that should send.
    """

    def setUp(self):
        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson",
        )
        self.agent = User.objects.create_user(
            email="agent@example.com", password="pass1234",
            first_name="Sam", last_name="Reid",
        )
        SupportScope.objects.create(user=self.agent)
        mail.outbox = []

    def make_ticket(self, **overrides):
        with self.captureOnCommitCallbacks(execute=True):
            ticket = lifecycle.create_ticket(
                user=self.requester,
                category=TicketCategory.PROGRAMS_GROUPS,
                subject="Cannot access group workspace",
                body="I get an error opening my group.",
                **overrides,
            )
        return ticket

    def quiet_ticket(self):
        """A ticket whose creation email has been cleared from the outbox."""
        ticket = self.make_ticket()
        mail.outbox = []
        return ticket


class SubmissionEmailTests(TicketEmailTestCase):
    def test_submitting_sends_exactly_one_email_to_the_requester(self):
        self.make_ticket()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["mia@example.com"])

    def test_the_subject_carries_the_ticket_number(self):
        ticket = self.make_ticket()
        self.assertIn(ticket.ticket_number, mail.outbox[0].subject)

    def test_it_says_where_the_ticket_stands_whose_move_it_is_and_when_to_expect_us(self):
        ticket = self.make_ticket()
        message = mail.outbox[0]
        html = message.alternatives[0][0]
        for element in (ticket.ticket_number, "Open", "do not need to do anything",
                        "one business day"):
            self.assertIn(element, html)

    def test_there_is_a_plain_text_body_as_well_as_the_html(self):
        self.make_ticket()
        message = mail.outbox[0]
        self.assertTrue(message.body.strip())
        self.assertEqual(message.alternatives[0][1], "text/html")

    def test_nothing_is_sent_before_the_transaction_commits(self):
        # Without the commit hook the requester could hold a receipt for a
        # ticket that a rollback erased.
        lifecycle.create_ticket(
            user=self.requester,
            category=TicketCategory.ACCOUNT_ACCESS,
            subject="Uncommitted",
            body="Nothing should go out yet.",
        )
        self.assertEqual(mail.outbox, [])


class ReplyEmailTests(TicketEmailTestCase):
    def test_a_support_reply_notifies_the_requester(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Looking into it.")
        self.assertEqual(len(mail.outbox), 1)

    def test_an_internal_note_notifies_nobody(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_internal_note(ticket=ticket, actor=self.agent, body="Internal only.")
        self.assertEqual(mail.outbox, [])

    def test_when_we_are_waiting_on_them_the_email_says_so(self):
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.mark_pending(ticket=ticket, actor=self.agent)
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent, body="Could you send a screenshot?"
            )

        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("waiting on your answer", html)

    def test_moving_a_ticket_to_pending_does_not_send_a_second_email(self):
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.mark_pending(ticket=ticket, actor=self.agent)
        self.assertEqual(mail.outbox, [])


class ResolutionEmailTests(TicketEmailTestCase):
    def test_resolving_sends_exactly_one_email(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.resolve(ticket=ticket, actor=self.agent)
        self.assertEqual(len(mail.outbox), 1)

    def test_resolving_twice_still_sends_only_one(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.resolve(ticket=ticket, actor=self.agent)
            lifecycle.resolve(ticket=ticket, actor=self.agent)
        self.assertEqual(len(mail.outbox), 1)

    def test_it_tells_them_replying_will_reopen_it(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.resolve(ticket=ticket, actor=self.agent)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Resolved", html)
        self.assertIn("reopen automatically", html)


class NoRecipientTests(TicketEmailTestCase):
    def test_a_ticket_with_no_requester_is_skipped_rather_than_failing(self):
        # Screening raises tickets with no requester at all. Every email in
        # the system has to step over those for their whole life, not just at
        # creation.
        ticket = self.quiet_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(
            created_by=None, channel=TicketChannel.AI_SCREENING
        )
        ticket.refresh_from_db()

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Reviewed.")
            lifecycle.resolve(ticket=ticket, actor=self.agent)

        self.assertEqual(mail.outbox, [])
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)


class SupportSideEmailTests(TicketEmailTestCase):
    def test_agents_are_never_emailed_about_their_own_queue(self):
        # E4 and E5 in the design: deliberately not built. Agents work from
        # the queue, so mail to them would be noise nobody reads.
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.claim(ticket=ticket, actor=self.agent)
            lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
            lifecycle.add_user_reply(
                ticket=ticket, user=self.requester, body="Any news?"
            )
        recipients = [address for message in mail.outbox for address in message.to]
        self.assertNotIn("agent@example.com", recipients)


@override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
class DeliveryFailureTests(TicketEmailTestCase):
    """DEC-012.

    Marking a ticket resolved says the requester was told. When the send
    fails that is no longer true, and a log line is not where an agent looks.
    """

    def resolve_with_a_dead_relay(self, ticket):
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=RuntimeError("smtp down")
        ):
            with self.captureOnCommitCallbacks(execute=True):
                lifecycle.resolve(ticket=ticket, actor=self.agent)

    def test_a_bounced_resolution_email_does_not_undo_the_resolution(self):
        ticket = self.quiet_ticket()
        self.resolve_with_a_dead_relay(ticket)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)
        self.assertIsNotNone(ticket.resolved_at)

    def test_the_failure_is_written_onto_the_timeline(self):
        ticket = self.quiet_ticket()
        self.resolve_with_a_dead_relay(ticket)

        last = ticket.messages.order_by("created_at").last()
        self.assertEqual(last.message_type, TicketMessageType.SYSTEM)
        self.assertIn("could not be delivered", last.body)
        self.assertIn("mia@example.com", last.body)

    def test_the_bounce_notice_does_not_float_the_ticket_for_the_requester(self):
        ticket = self.quiet_ticket()
        self.resolve_with_a_dead_relay(ticket)

        after = Ticket.objects.get(pk=ticket.pk)
        # resolve() moves all three clocks together, so the requester's clock
        # is still standing exactly where the resolution left it.
        self.assertEqual(after.updated_at, after.resolved_at)
        # The bounce notice landed afterwards and moved the support clock
        # only. Strictly greater is the whole point: if these were equal, the
        # notice had touched the requester's clock too.
        self.assertGreater(after.support_updated_at, after.updated_at)
        self.assertIn(
            "could not be delivered",
            ticket.messages.order_by("created_at").last().body,
        )
