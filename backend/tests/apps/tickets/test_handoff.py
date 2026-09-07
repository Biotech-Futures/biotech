from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from apps.audit.models import AuditLog
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


class ScreeningFixture(TestCase):
    """Fixture only, deliberately test-free.

    A class carrying tests must not be subclassed for its setUp: the child
    re-runs every one of the parent's cases under its own name, which inflates
    the count and makes a suite look better covered than it is.
    """

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


class ScreeningHandoffTests(ScreeningFixture):
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
        # An internal note, not SYSTEM: see EvidenceIsNeverRequesterVisibleTests.
        self.assertEqual(messages[0].message_type, TicketMessageType.INTERNAL_NOTE)
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

    def test_raising_a_screening_ticket_writes_an_audit_row(self):
        """A machine judging a minor's message has to leave a trail.

        Every other way a ticket changes state writes one; this path is the
        one where "what was flagged, by which layer, and when" matters most,
        because no person was involved to remember it.
        """
        ticket = self.raise_ticket()

        row = AuditLog.objects.get(
            entity_type="ticket", entity_id=ticket.pk, action="create"
        )
        self.assertIsNone(row.actor_user, "the screener is not a person")
        self.assertEqual(row.after_state["channel"], "ai_screening")
        self.assertEqual(row.after_state["ticket_number"], ticket.ticket_number)
        self.assertIn("screening_layer", row.after_state)

    def test_raising_a_screening_ticket_emails_nobody(self):
        self.raise_ticket()
        self.assertEqual(len(mail.outbox), 0)

    def test_the_category_is_the_platform_only_one(self):
        # Pinned against the literal, not against the constant. Comparing the
        # constant to itself passes for any value it is ever given, which
        # would let this move again without anyone being told.
        self.assertEqual(self.raise_ticket().category, "flagged_content")
        self.assertEqual(SCREENING_TICKET_CATEGORY, "flagged_content")

    def test_that_category_is_filterable_rather_than_falsy(self):
        """The empty string it used to carry was invisible to the queue.

        apply_filters skips falsy values, so "show me the flagged ones" was a
        filter that quietly returned everything. A real value is the whole
        point of having one.
        """
        from apps.tickets.services.queue import apply_filters

        ticket = self.raise_ticket()
        found = apply_filters(Ticket.objects.all(), category="flagged_content")
        self.assertEqual(list(found.values_list("pk", flat=True)), [ticket.pk])

    def test_a_requester_cannot_file_their_own_enquiry_under_it(self):
        """It is the platform's category, not a topic on the form.

        The submission serializer is built from its own list rather than from
        TicketCategory.choices precisely so that adding one here cannot open
        it to the public. This is the test that keeps those two in step.
        """
        from apps.tickets.serializers import TicketCreateSerializer

        serializer = TicketCreateSerializer(data={
            "category": "flagged_content",
            "subject": "Let me file this as a moderation case",
            "body": "Trying the category that is not mine to pick.",
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("category", serializer.errors)


class EvidenceIsNeverRequesterVisibleTests(ScreeningFixture):
    """The evidence file is a case file, so it is an internal note.

    It names the sender — falling back to their email address when the name
    is blank — and quotes the flagged private message word for word.

    Defence in depth on purpose. These tickets have no requester today
    (``created_by=None``), and the requester's queryset filters on ownership,
    so nothing reaches a student. But that guard says "this ticket has no
    owner", not "this text is never shown to a requester", and the two come
    apart the moment anything gives a screening ticket an owner. The message
    type is the guard that stays true either way.
    """

    def test_the_evidence_is_written_as_an_internal_note(self):
        ticket = self.raise_ticket()
        body = ticket.messages.first()

        self.assertEqual(body.message_type, TicketMessageType.INTERNAL_NOTE)

    def test_a_requester_on_such_a_ticket_would_still_not_see_it(self):
        """The property that matters, asserted end to end.

        Deliberately hands the ticket an owner, which production does not do,
        because the point is that the protection survives that happening. Run
        through the requester's own view function, not by re-implementing its
        filter here.
        """
        from apps.tickets.views import _visible_messages

        ticket = self.raise_ticket()
        ticket.created_by = self.sender
        ticket.save(update_fields=["created_by"])

        visible = "\n".join(m.body for m in _visible_messages(ticket))

        self.assertNotIn(self.sender.email, visible)
        self.assertNotIn("flagged by automated screening", visible)

    def test_support_can_still_read_it(self):
        """It has to reach the people it was written for."""
        ticket = self.raise_ticket()
        bodies = [m.body for m in ticket.messages.all()]

        self.assertTrue(
            any("flagged by automated screening" in b for b in bodies),
            "the evidence did not reach the support timeline at all",
        )
