from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
    TicketMessage,
    TicketMessageType,
    TicketStatus,
)
from apps.tickets.services import lifecycle, system_messages

User = get_user_model()


class LifecycleTestCase(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson",
        )
        self.agent = User.objects.create_user(
            email="agent@example.com", password="pass1234",
            first_name="Sam", last_name="Reid",
        )
        self.other_agent = User.objects.create_user(
            email="agent2@example.com", password="pass1234",
            first_name="Dana", last_name="Okafor",
        )
        SupportScope.objects.create(user=self.agent)
        SupportScope.objects.create(user=self.other_agent)

    def make_ticket(self, **overrides):
        payload = {
            "user": self.requester,
            "category": TicketCategory.PROGRAMS_GROUPS,
            "subject": "Cannot access group workspace",
            "body": "I get an error opening my group.",
        }
        payload.update(overrides)
        return lifecycle.create_ticket(**payload)

    def timeline(self, ticket):
        return list(ticket.messages.order_by("created_at"))


class CreateTicketTests(LifecycleTestCase):
    def test_a_new_ticket_opens_with_the_message_then_the_acknowledgement(self):
        ticket = self.make_ticket()
        types = [m.message_type for m in self.timeline(ticket)]
        self.assertEqual(
            types, [TicketMessageType.USER_MESSAGE, TicketMessageType.SYSTEM]
        )

    def test_the_acknowledgement_greets_the_requester_by_name(self):
        ticket = self.make_ticket()
        acknowledgement = self.timeline(ticket)[1]
        self.assertEqual(
            acknowledgement.body,
            "Thanks Mia. We're looking into this and will get back to you shortly.",
        )
        self.assertIsNone(acknowledgement.author_id)

    def test_a_new_ticket_gets_a_number_and_starts_open(self):
        ticket = self.make_ticket()
        self.assertRegex(ticket.ticket_number, r"^SUP-\d{4}-\d{5}$")
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertIsNone(ticket.assignee_id)

    def test_a_failed_insert_leaves_no_orphan_messages(self):
        existing = self.make_ticket()
        messages_before = TicketMessage.objects.count()
        tickets_before = Ticket.objects.count()

        with patch(
            "apps.tickets.services.lifecycle.allocate_ticket_number",
            return_value=existing.ticket_number,
        ):
            with self.assertRaises(IntegrityError):
                self.make_ticket(subject="Doomed by a duplicate number")

        self.assertEqual(Ticket.objects.count(), tickets_before)
        self.assertEqual(TicketMessage.objects.count(), messages_before)

    def test_region_is_snapshotted_as_empty_when_the_user_has_no_country(self):
        self.assertEqual(self.make_ticket().region, "")


class UserReplyTests(LifecycleTestCase):
    def test_a_reply_while_pending_hands_the_ball_back_to_support(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.mark_pending(ticket=ticket, actor=self.agent)
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)

        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="Here is the screenshot."
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)

    def test_a_reply_on_a_resolved_ticket_reopens_it_and_frees_the_owner(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)

        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="This is still broken."
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertIsNone(ticket.assignee_id)
        self.assertIsNone(ticket.resolved_at)
        self.assertEqual(
            self.timeline(ticket)[-1].body, system_messages.REOPENED
        )

    def test_the_reopen_audit_row_is_filed_under_the_requester(self):
        ticket = self.make_ticket()
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        lifecycle.add_user_reply(ticket=ticket, user=self.requester, body="Still broken.")

        row = AuditLog.objects.get(entity_type="ticket", action="reopen")
        self.assertEqual(row.actor_user_id, self.requester.pk)

    def test_somebody_elses_reply_is_refused_and_does_not_reopen(self):
        ticket = self.make_ticket()
        lifecycle.resolve(ticket=ticket, actor=self.agent)

        with self.assertRaises(PermissionDenied):
            lifecycle.add_user_reply(
                ticket=ticket, user=self.other_agent, body="Reopening on your behalf."
            )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)

    def test_a_reply_floats_an_older_ticket_above_a_newer_one(self):
        older = self.make_ticket(subject="Older")
        newer = self.make_ticket(subject="Newer")
        self.assertGreater(newer.updated_at, older.updated_at)

        lifecycle.add_user_reply(ticket=older, user=self.requester, body="Any update?")

        ordered = list(
            Ticket.objects.filter(created_by=self.requester).order_by("-updated_at")
        )
        self.assertEqual(ordered[0].pk, older.pk)


class SupportMessageTests(LifecycleTestCase):
    def test_the_first_support_reply_stamps_the_response_clock_once(self):
        ticket = self.make_ticket()
        self.assertIsNone(ticket.first_response_at)

        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Looking now.")
        first_stamp = ticket.first_response_at
        self.assertIsNotNone(first_stamp)

        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Still looking.")
        ticket.refresh_from_db()
        self.assertEqual(ticket.first_response_at, first_stamp)

    def test_a_support_reply_moves_both_clocks(self):
        ticket = self.make_ticket()
        before_user, before_support = ticket.updated_at, ticket.support_updated_at

        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Looking now.")
        ticket.refresh_from_db()
        self.assertGreater(ticket.updated_at, before_user)
        self.assertGreater(ticket.support_updated_at, before_support)

    def test_an_internal_note_never_moves_the_requesters_clock(self):
        ticket = self.make_ticket()
        before_user, before_support = ticket.updated_at, ticket.support_updated_at

        lifecycle.add_internal_note(
            ticket=ticket, actor=self.agent, body="Escalating to the platform team."
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.updated_at, before_user)
        self.assertGreater(ticket.support_updated_at, before_support)

    def test_an_internal_note_writes_no_audit_row(self):
        ticket = self.make_ticket()
        lifecycle.add_internal_note(ticket=ticket, actor=self.agent, body="Internal.")
        self.assertFalse(AuditLog.objects.filter(entity_type="ticket").exists())


class AssignmentTests(LifecycleTestCase):
    def test_picking_up_an_open_ticket_starts_it_and_says_so(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.assertEqual(ticket.assignee_id, self.agent.pk)
        self.assertEqual(
            self.timeline(ticket)[-1].body, system_messages.TICKET_NOW_HANDLED
        )

    def test_the_pickup_message_never_names_the_agent(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        body = self.timeline(ticket)[-1].body
        for leak in (self.agent.first_name, self.agent.last_name, self.agent.email):
            self.assertNotIn(leak, body)

    def test_handing_over_a_started_ticket_is_invisible_to_the_requester(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        messages_before = ticket.messages.count()
        before_user, before_support = ticket.updated_at, ticket.support_updated_at
        audit_before = AuditLog.objects.filter(entity_type="ticket", action="assign").count()

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.other_agent)

        ticket.refresh_from_db()
        self.assertEqual(ticket.assignee_id, self.other_agent.pk)
        self.assertEqual(ticket.messages.count(), messages_before)
        self.assertEqual(ticket.updated_at, before_user)
        self.assertGreater(ticket.support_updated_at, before_support)
        self.assertEqual(
            AuditLog.objects.filter(entity_type="ticket", action="assign").count(),
            audit_before + 1,
        )

    def test_the_assign_audit_row_records_both_sides_of_the_move(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.other_agent)

        row = AuditLog.objects.filter(entity_type="ticket", action="assign").latest("created_at")
        self.assertEqual(row.before_state, {"assignee_id": self.agent.pk})
        self.assertEqual(row.after_state, {"assignee_id": self.other_agent.pk})
        self.assertEqual(row.actor_user_id, self.agent.pk)

    def test_bulk_assign_only_starts_the_tickets_that_were_waiting_in_the_pool(self):
        open_ticket = self.make_ticket(subject="Still in the pool")
        pending_ticket = self.make_ticket(subject="Waiting on the requester")
        lifecycle.claim(ticket=pending_ticket, actor=self.agent)
        lifecycle.mark_pending(ticket=pending_ticket, actor=self.agent)

        pending_messages_before = pending_ticket.messages.count()
        results = lifecycle.bulk_assign(
            ticket_ids=[open_ticket.pk, pending_ticket.pk, 999999],
            assignee=self.other_agent,
            actor=self.agent,
        )

        self.assertEqual(
            results,
            [
                {"ticketId": open_ticket.pk, "ok": True},
                {"ticketId": pending_ticket.pk, "ok": True},
                {"ticketId": 999999, "ok": False, "error": "not found"},
            ],
        )

        open_ticket.refresh_from_db()
        pending_ticket.refresh_from_db()
        self.assertEqual(open_ticket.status, TicketStatus.IN_PROGRESS)
        # The one that was waiting on the requester keeps its status.
        self.assertEqual(pending_ticket.status, TicketStatus.PENDING_USER)
        self.assertEqual(pending_ticket.assignee_id, self.other_agent.pk)
        self.assertEqual(pending_ticket.messages.count(), pending_messages_before)


class ResolveTests(LifecycleTestCase):
    def test_resolving_stamps_the_clock_and_tells_the_requester_how_to_come_back(self):
        ticket = self.make_ticket()
        self.assertTrue(lifecycle.resolve(ticket=ticket, actor=self.agent))

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)
        self.assertIsNotNone(ticket.resolved_at)
        self.assertEqual(self.timeline(ticket)[-1].body, system_messages.RESOLVED)

    def test_resolving_twice_changes_nothing_the_second_time(self):
        ticket = self.make_ticket()
        self.assertTrue(lifecycle.resolve(ticket=ticket, actor=self.agent))
        messages_after_first = ticket.messages.count()

        self.assertFalse(lifecycle.resolve(ticket=ticket, actor=self.agent))

        ticket.refresh_from_db()
        self.assertEqual(ticket.messages.count(), messages_after_first)
        self.assertEqual(
            AuditLog.objects.filter(entity_type="ticket", action="resolve").count(), 1
        )

    def test_the_resolve_audit_row_carries_both_states(self):
        ticket = self.make_ticket()
        lifecycle.resolve(ticket=ticket, actor=self.agent)

        row = AuditLog.objects.get(entity_type="ticket", action="resolve")
        self.assertEqual(row.before_state["status"], TicketStatus.OPEN)
        self.assertEqual(row.after_state["status"], TicketStatus.RESOLVED)
        self.assertIsNotNone(row.after_state["resolved_at"])
        self.assertEqual(row.actor_user_id, self.agent.pk)


class SetStatusTests(LifecycleTestCase):
    def test_correcting_the_status_writes_a_neutral_message_and_an_audit_row(self):
        ticket = self.make_ticket()
        self.assertTrue(
            lifecycle.set_status(
                ticket=ticket, new_status=TicketStatus.IN_PROGRESS, actor=self.agent
            )
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.assertEqual(self.timeline(ticket)[-1].body, "Status changed to In progress.")
        row = AuditLog.objects.get(entity_type="ticket", action="status")
        self.assertEqual(row.before_state, {"status": TicketStatus.OPEN})
        self.assertEqual(row.after_state, {"status": TicketStatus.IN_PROGRESS})

    def test_correcting_the_status_never_touches_the_owner(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.OPEN, actor=self.other_agent
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertEqual(ticket.assignee_id, self.agent.pk)

    def test_dragging_a_resolved_ticket_back_to_open_invents_no_reply(self):
        ticket = self.make_ticket()
        lifecycle.resolve(ticket=ticket, actor=self.agent)

        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.OPEN, actor=self.agent
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertIsNone(ticket.resolved_at)
        # No fake user_message, and the audit row is the agent's, not the
        # requester's — this is not the T7 path.
        self.assertFalse(
            AuditLog.objects.filter(entity_type="ticket", action="reopen").exists()
        )
        self.assertEqual(
            ticket.messages.filter(message_type=TicketMessageType.USER_MESSAGE).count(), 1
        )

    def test_landing_on_resolved_goes_through_the_resolve_path(self):
        ticket = self.make_ticket()
        self.assertTrue(
            lifecycle.set_status(
                ticket=ticket, new_status=TicketStatus.RESOLVED, actor=self.agent
            )
        )
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.resolved_at)
        self.assertTrue(
            AuditLog.objects.filter(entity_type="ticket", action="resolve").exists()
        )

    def test_setting_the_status_it_already_has_is_a_no_op(self):
        ticket = self.make_ticket()
        messages_before = ticket.messages.count()
        self.assertFalse(
            lifecycle.set_status(
                ticket=ticket, new_status=TicketStatus.OPEN, actor=self.agent
            )
        )
        self.assertEqual(ticket.messages.count(), messages_before)
