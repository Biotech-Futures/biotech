from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from apps.groups.models import Countries
from apps.tickets.models import (
    Ticket,
    TicketChannel,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
)
from apps.tickets.services.handoff import (
    SCREENING_TICKET_CATEGORY,
    create_ticket_from_screening,
)

User = get_user_model()


def fake_verdict(*, layer="rule", category="personal_contact", reason="phone number"):
    """Stand-in for screening's Verdict — that app does not exist yet."""
    return SimpleNamespace(flagged=True, layer=layer, category=category, reason=reason)


class ScreeningHandoffTests(TestCase):
    def setUp(self):
        self.country = Countries.objects.create(country_name="Australia")
        self.sender = User.objects.create_user(
            email="student@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson", country=self.country,
        )
        self.group = SimpleNamespace(pk=7, group_name="Team Photosynthesis")
        self.message = SimpleNamespace(
            pk=42, group=self.group, sender_user=self.sender
        )

    def raise_ticket(self, **overrides):
        kwargs = {
            "message": self.message,
            "verdict": fake_verdict(),
            "text_snapshot": "call me on 0400 000 000",
        }
        kwargs.update(overrides)
        return create_ticket_from_screening(
            kwargs["message"], kwargs["verdict"], kwargs["text_snapshot"]
        )

    def test_the_ticket_is_marked_as_coming_from_screening_and_has_no_requester(self):
        ticket = self.raise_ticket()
        self.assertEqual(ticket.channel, TicketChannel.AI_SCREENING)
        self.assertIsNone(ticket.created_by_id)
        self.assertEqual(ticket.status, TicketStatus.OPEN)

    def test_it_gets_a_normal_ticket_number(self):
        self.assertRegex(self.raise_ticket().ticket_number, r"^SUP-\d{4}-\d{5}$")

    def test_region_is_snapshotted_from_the_message_sender(self):
        self.assertEqual(self.raise_ticket().region, "Australia")

    def test_an_llm_verdict_is_high_priority(self):
        ticket = self.raise_ticket(verdict=fake_verdict(layer="llm"))
        self.assertEqual(ticket.priority, TicketPriority.HIGH)

    def test_a_rule_verdict_is_normal_priority(self):
        ticket = self.raise_ticket(verdict=fake_verdict(layer="rule"))
        self.assertEqual(ticket.priority, TicketPriority.NORMAL)

    def test_an_unrecognised_layer_falls_back_to_normal_not_high(self):
        # A configured LLM that times out degrades to the rule layer. Reading
        # "is a key set?" instead of the layer would mark that path High and
        # flood the queue.
        ticket = self.raise_ticket(verdict=fake_verdict(layer=""))
        self.assertEqual(ticket.priority, TicketPriority.NORMAL)

    def test_the_subject_follows_the_agreed_shape(self):
        ticket = self.raise_ticket()
        self.assertEqual(
            ticket.subject,
            'AI screening: personal_contact — group "Team Photosynthesis"',
        )

    def test_a_very_long_group_name_cannot_overflow_the_subject_column(self):
        long_name = "G" * 255
        ticket = self.raise_ticket(
            message=SimpleNamespace(
                pk=43,
                group=SimpleNamespace(pk=8, group_name=long_name),
                sender_user=self.sender,
            )
        )
        self.assertLessEqual(
            len(ticket.subject), Ticket._meta.get_field("subject").max_length
        )
        self.assertIn("…", ticket.subject)

    def test_the_only_timeline_entry_is_the_evidence_note(self):
        ticket = self.raise_ticket()
        messages = list(ticket.messages.all())
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_type, TicketMessageType.SYSTEM)
        self.assertIsNone(messages[0].author_id)

    def test_the_evidence_note_carries_the_text_as_it_was_when_flagged(self):
        ticket = self.raise_ticket(text_snapshot="the original wording")
        body = ticket.messages.get().body
        self.assertIn("the original wording", body)
        self.assertIn("rule", body)
        self.assertIn("phone number", body)
        self.assertIn("Team Photosynthesis", body)
        self.assertIn("Mia Thompson", body)

    @override_settings(ADMIN_FRONTEND_BASE_URL="https://admin.example.org")
    def test_the_evidence_note_links_back_to_this_ticket_and_points_at_the_group(self):
        ticket = self.raise_ticket()
        body = ticket.messages.get().body
        self.assertIn(f"https://admin.example.org/tickets?ticket={ticket.pk}", body)
        # The group conversation is a modal with no address of its own, so
        # this half is directions rather than a link.
        self.assertIn("Admin → Groups → Team Photosynthesis (group id 7) → Messages", body)

    def test_raising_a_screening_ticket_emails_nobody(self):
        self.raise_ticket()
        self.assertEqual(len(mail.outbox), 0)

    def test_the_category_is_the_deferred_placeholder(self):
        # Pinned so the open question cannot be closed by accident: the day
        # SCREENING_TICKET_CATEGORY changes, this test says so.
        self.assertEqual(self.raise_ticket().category, SCREENING_TICKET_CATEGORY)
