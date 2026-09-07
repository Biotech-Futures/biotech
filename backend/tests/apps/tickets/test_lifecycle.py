import threading
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
    TicketMessage,
    TicketMessageType,
    TicketStatus,
)
from apps.tickets.services import lifecycle, queue, system_messages
from apps.tickets.services.handoff import create_ticket_from_screening

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
            "category": TicketCategory.HELP_STUDENT_GROUP,
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

    def test_region_is_snapshotted_from_the_requesters_country(self):
        # The positive half. Only the empty case was pinned, so the snapshot
        # could be blanked entirely and the suite stayed green — and with it
        # the region filter, the Unknown bucket, and the p52 region split all
        # quietly emptied out for every new ticket.
        from apps.groups.models import Countries

        country = Countries.objects.create(country_name="Australia")
        traveller = User.objects.create_user(
            email="lena@example.com", password="pass1234",
            first_name="Lena", last_name="Okafor", country=country,
        )
        self.assertEqual(self.make_ticket(user=traveller).region, "Australia")

    def test_a_portal_ticket_writes_no_audit_row(self):
        """Pinned because it is a decision, not because it is an accident.

        工单系统-完整说明.md §9.4 settles it: the person who filled the form in
        is the record, and created_by already carries them. Screening writes a
        create row because there is nobody on that path. The visible cost is
        that the audit page's Created filter answers with screening tickets
        only, and that page carries a sentence saying so.

        Here so that anybody adding the row has to change this line and read
        that sentence, rather than discovering afterwards that the admin page
        now contradicts itself.
        """
        self.make_ticket()
        self.assertEqual(
            list(
                AuditLog.objects.filter(entity_type="ticket").values_list(
                    "action", flat=True
                )
            ),
            [],
        )

    def test_the_first_message_is_signed_by_the_requester(self):
        # The timeline's opening message carries the requester's name; drop
        # the author and it renders as an anonymous system line, and the
        # requester's own words look like something the platform said.
        ticket = self.make_ticket()
        self.assertEqual(self.timeline(ticket)[0].author_id, self.requester.pk)


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

class ConcurrentChangeTests(LifecycleTestCase):
    """What happens when the row moves while a request is still holding it.

    The requester's instance is read at the top of the view, then the request
    spends the attachment upload — a round trip to Azure — before lifecycle
    ever sees it. An agent working the queue in that window commits a status
    change the in-memory object knows nothing about. These tests hold a stale
    instance on purpose, which is exactly what the upload window produces.
    """

    def test_a_reply_reopens_a_ticket_that_was_resolved_during_the_upload(self):
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        stale = Ticket.objects.get(pk=ticket.pk)      # what the view is holding
        self.assertEqual(stale.status, TicketStatus.IN_PROGRESS)

        # The agent resolves it while the files are still going up.
        lifecycle.resolve(ticket=Ticket.objects.get(pk=ticket.pk), actor=self.agent)

        lifecycle.add_user_reply(
            ticket=stale, user=self.requester, body="Still stuck, please help.",
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertIsNone(ticket.assignee_id)
        self.assertIsNone(ticket.resolved_at)
        self.assertTrue(
            TicketMessage.objects.filter(
                ticket=ticket, body=system_messages.REOPENED
            ).exists(),
            "the requester was promised the ticket would reopen automatically",
        )
        self.assertTrue(
            AuditLog.objects.filter(
                entity_type=lifecycle.AUDIT_ENTITY_TYPE,
                entity_id=ticket.pk,
                action="reopen",
            ).exists(),
            "p52 counts reopens from the audit log",
        )

    def test_a_reply_does_not_resurrect_a_resolution_date(self):
        """The other half of the same race, from pending_user.

        A stale PENDING_USER matched the old code's second branch and wrote
        in_progress straight over a committed resolve, leaving resolved_at
        set on a ticket that is not resolved — a state the machine does not
        have, and one that makes "time to resolve" measure a resolution that
        was undone.
        """
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        lifecycle.mark_pending(ticket=ticket, actor=self.agent)
        stale = Ticket.objects.get(pk=ticket.pk)
        self.assertEqual(stale.status, TicketStatus.PENDING_USER)

        lifecycle.resolve(ticket=Ticket.objects.get(pk=ticket.pk), actor=self.agent)
        lifecycle.add_user_reply(
            ticket=stale, user=self.requester, body="Here is the screenshot.",
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertIsNone(ticket.resolved_at)

    def test_a_ticket_deleted_mid_request_stops_every_write(self):
        """The window a delete opens on requests already in flight.

        A request that uploads attachments holds its ticket instance for
        seconds. If an admin deletes it in that gap, whatever we write lands
        on a row that is invisible to the requester AND to the queue — which
        is the "black hole" DEC-024 rejected option B to avoid. The race
        recreates it, so every write path has to fail instead.
        """
        for label, call in [
            ("requester reply", lambda t: lifecycle.add_user_reply(
                ticket=t, user=self.requester, body="Still stuck.")),
            ("support reply", lambda t: lifecycle.add_support_reply(
                ticket=t, actor=self.agent, body="Looking into it.")),
            ("internal note", lambda t: lifecycle.add_internal_note(
                ticket=t, actor=self.agent, body="For us only.")),
            ("status change", lambda t: lifecycle.set_status(
                ticket=t, new_status=TicketStatus.PENDING_USER, actor=self.agent)),
            ("hand-off", lambda t: lifecycle.assign(
                ticket=t, actor=self.agent, assignee=self.other_agent)),
            ("mark pending", lambda t: lifecycle.mark_pending(
                ticket=t, actor=self.agent)),
            # Joined this family when resolve() was given the row lock the
            # other five always had. It used to guard with its conditional
            # update alone, which refused the write correctly but reported it
            # by returning False, and the view read no return value and
            # answered 200 "Ticket updated successfully".
            ("resolve", lambda t: lifecycle.resolve(ticket=t, actor=self.agent)),
        ]:
            with self.subTest(action=label):
                ticket = self.make_ticket()
                stale = Ticket.objects.get(pk=ticket.pk)   # what the view holds
                lifecycle.soft_delete(
                    ticket=Ticket.objects.get(pk=ticket.pk), actor=self.agent
                )
                before = TicketMessage.objects.filter(ticket=ticket).count()

                with self.assertRaises(lifecycle.TicketGone):
                    call(stale)

                self.assertEqual(
                    TicketMessage.objects.filter(ticket=ticket).count(),
                    before,
                    f"{label} wrote onto a deleted ticket",
                )

    def test_resolving_a_deleted_ticket_sends_no_email(self):
        """The consequence the loop above does not check: no email.

        resolve() is the one path that decides by itself whether the "we're
        done" email goes out, so refusing has to happen before the send is
        scheduled — otherwise a student is told their enquiry is resolved and
        the link in the email 404s.

        ⚠️ The contract changed here. This used to assert that resolve()
        returned False, which was true and was also the defect: refusing by
        return value meant the view, which read no return value, answered 200
        "Ticket updated successfully" while the ticket sat untouched. It now
        raises TicketGone like the other five write paths, and the view turns
        that into the 404 it always gave for the rest of them.
        """
        ticket = self.make_ticket()
        stale = Ticket.objects.get(pk=ticket.pk)
        lifecycle.soft_delete(ticket=Ticket.objects.get(pk=ticket.pk), actor=self.agent)

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(lifecycle.TicketGone):
                lifecycle.resolve(ticket=stale, actor=self.agent)

        ticket.refresh_from_db()
        self.assertNotEqual(ticket.status, TicketStatus.RESOLVED)
        self.assertEqual(mail.outbox, [])

    def test_picking_up_is_decided_on_the_committed_status(self):
        """A hand-off must not announce itself to the requester.

        `_assign_one` reads the status to tell "someone picked this out of the
        pool" (which the requester is told about) from "an agent passed it to
        a colleague" (which is none of their business, DEC-017/D1). Read from
        a stale OPEN instance, a hand-off writes the pick-up message and
        bumps the requester's clock.
        """
        ticket = self.make_ticket()
        stale = Ticket.objects.get(pk=ticket.pk)
        self.assertEqual(stale.status, TicketStatus.OPEN)

        lifecycle.assign(
            ticket=Ticket.objects.get(pk=ticket.pk),
            actor=self.agent,
            assignee=self.agent,
        )
        before = Ticket.objects.get(pk=ticket.pk).updated_at

        lifecycle.assign(ticket=stale, actor=self.agent, assignee=self.other_agent)

        ticket.refresh_from_db()
        self.assertEqual(ticket.assignee_id, self.other_agent.pk)
        self.assertEqual(
            TicketMessage.objects.filter(
                ticket=ticket, body=system_messages.TICKET_NOW_HANDLED
            ).count(),
            1,
            "the hand-off announced itself a second time",
        )
        self.assertEqual(ticket.updated_at, before, "a hand-off moved the requester's clock")


@skipUnlessDBFeature("has_select_for_update")
class RowLockTests(TransactionTestCase):
    """``_lock()``'s FOR UPDATE clause, tested as a lock and not as a re-read.

    Every other test that touches ``_lock`` exercises the ``refresh_from_db``
    half of it: they hand in a stale instance and check the decision came from
    the committed row. Taking ``select_for_update()`` off and leaving the
    refresh passes all of them, because with nothing else running the plain
    read returns the same value.

    What the clause buys is that a *second* writer waits. Without it two
    requests both read the committed row, both decide from it, and both write
    — the lost update the whole lifecycle layer is built to avoid. Proving
    that needs two live connections, so: TransactionTestCase, real threads,
    and Postgres only (Django drops FOR UPDATE on SQLite without saying so).
    """

    HOLD_SECONDS = 0.5

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
        self.ticket = lifecycle.create_ticket(
            user=self.requester,
            category=TicketCategory.HELP_STUDENT_GROUP,
            subject="Cannot access group workspace",
            body="I get an error opening my group.",
        )
        lifecycle.claim(ticket=self.ticket, actor=self.agent)

    def test_a_second_writer_waits_for_the_first_to_commit(self):
        """The clause itself: measured, because it has no other visible effect."""
        holding = threading.Event()
        may_commit = threading.Event()
        waited_for = []
        failures = []

        def holder():
            try:
                with transaction.atomic():
                    lifecycle._lock(Ticket.objects.get(pk=self.ticket.pk))
                    holding.set()
                    may_commit.wait(timeout=10)
            except Exception as exc:
                failures.append(("holder", exc))
            finally:
                connection.close()

        def waiter():
            try:
                if not holding.wait(timeout=10):
                    failures.append(("waiter", RuntimeError("holder never locked")))
                    return
                started = time.monotonic()
                with transaction.atomic():
                    lifecycle._lock(Ticket.objects.get(pk=self.ticket.pk))
                waited_for.append(time.monotonic() - started)
            except Exception as exc:
                failures.append(("waiter", exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=holder), threading.Thread(target=waiter)]
        for thread in threads:
            thread.start()
        holding.wait(timeout=10)
        time.sleep(self.HOLD_SECONDS)
        may_commit.set()
        for thread in threads:
            thread.join(timeout=15)

        self.assertEqual(failures, [])
        self.assertEqual(len(waited_for), 1, "the second writer never finished")
        self.assertGreater(
            waited_for[0], self.HOLD_SECONDS * 0.8,
            "the second writer got the row while the first still held it — "
            "FOR UPDATE is not doing anything",
        )

    def test_a_reply_racing_a_resolve_still_reopens_the_ticket(self):
        """What the clause is for, in the words of the promise it keeps.

        The platform tells the requester, in ``system_messages.RESOLVED``,
        that replying reopens the ticket. An agent resolving while the
        requester's reply is in flight is the case that tests it: the reply
        has to be decided against the resolve, not against the status the
        request read on the way in.

        Sequenced deliberately rather than raced: the resolver holds an open
        transaction while the reply starts, so an unlocked read would see the
        *old* status and skip the reopen. That makes the failure deterministic
        instead of a coin toss.
        """
        resolver_holding = threading.Event()
        reply_started = threading.Event()
        failures = []

        def resolver():
            try:
                with transaction.atomic():
                    lifecycle.resolve(
                        ticket=Ticket.objects.get(pk=self.ticket.pk), actor=self.agent
                    )
                    resolver_holding.set()
                    reply_started.wait(timeout=10)
                    # And then keep holding. Releasing on the signal alone is
                    # a race the wrong way: the replier sets it *before* its
                    # read, so this transaction could commit first, the
                    # replier would see RESOLVED even with no lock, and the
                    # test would pass on broken code. Holding through the
                    # read is what makes an unlocked read observably wrong.
                    time.sleep(self.HOLD_SECONDS)
            except Exception as exc:
                failures.append(("resolver", exc))
            finally:
                connection.close()

        def replier():
            try:
                if not resolver_holding.wait(timeout=10):
                    failures.append(("replier", RuntimeError("resolve never ran")))
                    return
                reply_started.set()
                lifecycle.add_user_reply(
                    ticket=Ticket.objects.get(pk=self.ticket.pk),
                    user=self.requester,
                    body="Still stuck, sorry.",
                )
            except Exception as exc:
                failures.append(("replier", exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=resolver), threading.Thread(target=replier)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertEqual(failures, [])
        self.ticket.refresh_from_db()
        self.assertEqual(
            self.ticket.status, TicketStatus.OPEN,
            "the requester replied after the resolve and the ticket stayed "
            "resolved — the platform told them it would reopen",
        )
        self.assertIsNone(self.ticket.assignee_id, "a reopened ticket keeps no owner (DEC-008)")
        self.assertTrue(
            AuditLog.objects.filter(
                entity_type=lifecycle.AUDIT_ENTITY_TYPE,
                entity_id=self.ticket.pk,
                action="reopen",
            ).exists(),
            "no reopen row: nothing records that this ticket came back",
        )


class MarkPendingTests(LifecycleTestCase):
    """T4's helper, brought up to the standard of the other write paths.

    It had no production caller, which is exactly why its two gaps survived
    every review: nothing exercised them. Phase 1a gives it a caller.
    """

    def test_marking_pending_clears_the_resolution_date(self):
        ticket = self.make_ticket()
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        self.assertIsNotNone(ticket.resolved_at)

        lifecycle.mark_pending(ticket=ticket, actor=self.agent)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        # Without this, the ticket reports a resolution that was undone, and
        # every p52 resolution-time figure computed from it is fiction.
        self.assertIsNone(ticket.resolved_at)

    def test_the_audit_row_records_the_committed_before_status(self):
        ticket = self.make_ticket()
        stale = Ticket.objects.get(pk=ticket.pk)
        # Committed by someone else after our instance was read.
        Ticket.objects.filter(pk=ticket.pk).update(status=TicketStatus.IN_PROGRESS)

        lifecycle.mark_pending(ticket=stale, actor=self.agent)

        row = AuditLog.objects.filter(
            entity_type="ticket", entity_id=ticket.pk, action="status"
        ).latest("created_at")
        self.assertEqual(row.before_state["status"], TicketStatus.IN_PROGRESS)


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentDeleteTests(TransactionTestCase):
    """Two admins delete the same ticket at the same moment.

    Exactly one may win. The loser must see TicketGone (from the lock's
    re-read) or a no-op (from the conditional update) — never a second audit
    row, because "deleted twice by two people" is a record of an event that
    cannot have happened, in the one place that has to stay trustworthy.
    """

    def setUp(self):
        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson",
        )
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pass1234",
            first_name="Ada", last_name="Lin",
        )
        self.ticket = lifecycle.create_ticket(
            user=self.requester,
            category=TicketCategory.HELP_STUDENT_GROUP,
            subject="Spam",
            body="Delete me twice.",
        )

    def test_two_concurrent_deletes_write_exactly_one_audit_row(self):
        start = threading.Barrier(2, timeout=10)
        outcomes = []
        failures = []

        def worker():
            try:
                start.wait()
                outcomes.append(
                    lifecycle.soft_delete(
                        ticket=Ticket.objects.get(pk=self.ticket.pk),
                        actor=self.admin,
                    )
                )
            except Exception as exc:
                failures.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        self.assertEqual(failures, [])
        self.assertEqual(sorted(outcomes), [False, True], "both deletes claimed the win")
        self.assertEqual(
            AuditLog.objects.filter(
                entity_type="ticket", entity_id=self.ticket.pk, action="delete"
            ).count(),
            1,
            "the audit trail records a deletion that happened twice",
        )
class ReplyAndMoveToPendingTests(LifecycleTestCase):
    """T4 folded into the reply that asks the question.

    Before this existed the admin app sent two requests, and the email went
    out between them — so the status it read was never the one the agent
    meant. See test_emails.ReplyAndMoveToPendingEmailTests for that half.
    """

    def test_replying_and_moving_lands_the_status_and_one_system_message(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        before = len(self.timeline(ticket))

        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent,
            body="Could you send a screenshot?", move_to_pending=True,
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        added = self.timeline(ticket)[before:]
        self.assertEqual(
            [m.message_type for m in added],
            [TicketMessageType.SUPPORT_REPLY, TicketMessageType.SYSTEM],
        )
        self.assertEqual(added[1].body, system_messages.MOVED_TO_PENDING_USER)

    def test_replying_and_moving_files_one_status_audit_row(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        before = AuditLog.objects.filter(entity_type="ticket", action="status").count()

        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent, body="Screenshot please.",
            move_to_pending=True,
        )

        rows = AuditLog.objects.filter(entity_type="ticket", action="status")
        self.assertEqual(rows.count(), before + 1)
        row = rows.order_by("-created_at").first()
        self.assertEqual(row.actor_user_id, self.agent.pk)
        self.assertEqual(row.before_state["status"], TicketStatus.IN_PROGRESS)
        self.assertEqual(row.after_state["status"], TicketStatus.PENDING_USER)

    def test_a_plain_reply_still_leaves_the_status_alone(self):
        """The flag defaults off, so every existing caller behaves as before."""
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent, body="Looking into it now."
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.assertFalse(
            ticket.messages.filter(
                body=system_messages.MOVED_TO_PENDING_USER
            ).exists()
        )

    def test_replying_again_while_already_pending_does_not_stack_a_message(self):
        """Two "and wait for them" replies in a row are one status change.

        Without the guard the timeline collects a "moved to pending user" line
        per reply, which reads as if the agent kept doing something.
        """
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent, body="Screenshot please.",
            move_to_pending=True,
        )
        system_rows = ticket.messages.filter(
            body=system_messages.MOVED_TO_PENDING_USER
        ).count()
        audit_rows = AuditLog.objects.filter(
            entity_type="ticket", action="status"
        ).count()

        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent, body="Any luck with that screenshot?",
            move_to_pending=True,
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        self.assertEqual(
            ticket.messages.filter(
                body=system_messages.MOVED_TO_PENDING_USER
            ).count(),
            system_rows,
        )
        self.assertEqual(
            AuditLog.objects.filter(entity_type="ticket", action="status").count(),
            audit_rows,
        )

    def test_moving_a_resolved_ticket_to_pending_clears_the_resolution_date(self):
        """resolved_at goes with the status — the rule reopen(), set_status()
        and the requester's reply all follow, and the one mark_pending() never
        did because production never called it. An agent asking one more
        question on a resolved ticket would otherwise leave a resolution date
        behind on a ticket that is no longer resolved, and "time to resolve"
        is computed from that column.
        """
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.resolved_at)

        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent,
            body="One more thing before we close this off.",
            move_to_pending=True,
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        self.assertIsNone(ticket.resolved_at)


class AssigningToTheCurrentOwnerDoesNothingTests(LifecycleTestCase):
    """Re-assigning a ticket to the person who already owns it is a no-op.

    It used to write an audit row reading "assignee 11 -> assignee 11" every
    time. Three consequences, and the first is the one that matters: the p52
    dashboard counts assign rows whose owner changed as hand-offs, so a
    measure the client asked for could be inflated by clicking a name already
    selected in the dropdown. The row also prints as an unreadable
    "Owner set to #11" on the audit page, and the write moved the support
    clock, lifting the ticket to the top of the queue.

    The PATCH view's priority branch has had this guard from the start; the
    assignee path did not inherit it.
    """

    def audit_rows(self, ticket):
        return AuditLog.objects.filter(
            entity_type="ticket", entity_id=ticket.pk, action="assign"
        ).count()

    def test_it_writes_no_audit_row(self):
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        before = self.audit_rows(ticket)

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)

        self.assertEqual(
            self.audit_rows(ticket), before,
            "clicking a name already selected forged hand-offs",
        )

    def test_it_does_not_lift_the_ticket_up_the_queue(self):
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        ticket.refresh_from_db()
        before = ticket.support_updated_at

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)

        ticket.refresh_from_db()
        self.assertEqual(ticket.support_updated_at, before)

    def test_it_does_not_tell_the_requester_anything_a_second_time(self):
        """The pick-up message is the one the requester reads.

        Assigning an open ticket posts "Your ticket is now being handled".
        Repeating the same assignment must not repeat it.
        """
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        before = ticket.messages.count()

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)

        self.assertEqual(ticket.messages.count(), before)

    def test_a_real_change_of_owner_still_records(self):
        """The guard must not swallow the case it exists to distinguish."""
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        before = self.audit_rows(ticket)

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.other_agent)

        self.assertEqual(self.audit_rows(ticket), before + 1)
        ticket.refresh_from_db()
        self.assertEqual(ticket.assignee_id, self.other_agent.pk)

    def test_handing_a_ticket_back_to_the_pool_still_records(self):
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        before = self.audit_rows(ticket)

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=None)

        self.assertEqual(self.audit_rows(ticket), before + 1)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.assignee_id)


class HandBackReleasesTheStatusTests(LifecycleTestCase):
    """Releasing a ticket is the pick-up run backwards.

    Left in "in progress" with nobody on it, the queue carried a row whose
    status column said somebody was working it and whose owner column said
    nobody was, and the requester's own page went on telling them their
    ticket was being handled.
    """

    def test_releasing_an_in_progress_ticket_puts_it_back_in_the_open_pool(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=None)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertIsNone(ticket.assignee_id)

    def test_releasing_still_says_nothing_to_the_requester(self):
        """The status they read is corrected, and that is all.

        "Nobody is on it just now" is not a sentence this product sends, and
        lifting the ticket to the top of their list would put it in front of
        them for something there is nothing to read about (DEC-017).
        """
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        messages_before = ticket.messages.count()
        updated_before = ticket.updated_at

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=None)

        ticket.refresh_from_db()
        self.assertEqual(ticket.messages.count(), messages_before)
        self.assertEqual(ticket.updated_at, updated_before)

    def test_releasing_leaves_the_overdue_clock_where_it_was(self):
        """Ownership changes never move the anchor, in either direction.

        The ball came to support when the requester raised the ticket, and
        putting it down does not hand it back to them.
        """
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        anchor = ticket.awaiting_support_since

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=None)

        ticket.refresh_from_db()
        self.assertEqual(ticket.awaiting_support_since, anchor)

    def test_a_ticket_waiting_on_the_requester_keeps_its_status(self):
        """The ball is not ours, so losing an owner does not make it ours."""
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.mark_pending(ticket=ticket, actor=self.agent)

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=None)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        self.assertIsNone(ticket.assignee_id)

    def test_a_resolved_ticket_keeps_its_status(self):
        """A finished ticket is not reopened by its owner letting go of it."""
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.resolve(ticket=ticket, actor=self.agent)

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=None)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)
        self.assertIsNone(ticket.assignee_id)

    def test_a_hand_off_between_agents_leaves_the_status_alone(self):
        """The guard the branch above must not swallow."""
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.other_agent)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.assertEqual(ticket.assignee_id, self.other_agent.pk)


class TimestampsAreReadUnderTheLockTests(LifecycleTestCase):
    """A write records the moment it held the row, not the moment it asked.

    Waiting for the row lock takes as long as the writer in front takes to
    commit. A clock read before that wait stamps the ticket earlier than
    every row the transaction then writes, so a resolve that queued behind
    the first support reply recorded a resolution that had happened before
    the ticket was ever answered.
    """

    def watched_lock(self):
        """Stand in for the wait, and report when the row was really held."""
        real_lock = lifecycle._lock
        held = []

        def watched(ticket):
            time.sleep(0.01)
            real_lock(ticket)
            held.append(timezone.now())

        return watched, held

    def test_the_resolution_time_is_read_after_the_row_is_held(self):
        ticket = self.make_ticket()
        watched, held = self.watched_lock()

        with patch.object(lifecycle, "_lock", watched):
            lifecycle.resolve(ticket=ticket, actor=self.agent)

        ticket.refresh_from_db()
        self.assertEqual(len(held), 1)
        self.assertGreaterEqual(
            ticket.resolved_at, held[0],
            "resolved_at predates the moment the resolve took the row",
        )

    def test_the_deletion_time_is_read_after_the_row_is_held(self):
        ticket = self.make_ticket()
        watched, held = self.watched_lock()

        with patch.object(lifecycle, "_lock", watched):
            lifecycle.soft_delete(ticket=ticket, actor=self.agent)

        ticket.refresh_from_db()
        self.assertEqual(len(held), 1)
        self.assertGreaterEqual(
            ticket.deleted_at, held[0],
            "deleted_at predates the moment the delete took the row",
        )


class ThePickUpIsAnnouncedOncePerSpellTests(LifecycleTestCase):
    """"Your ticket is now being handled." is said once, not once per click.

    Handing a ticket back is deliberately silent, so the sentence from the
    last pick-up is still the last thing the requester was told. Taking the
    ticket back therefore has nothing new to tell them, and repeating it is a
    line an agent can stack up by clicking the owner dropdown, moving the
    requester's clock and floating the ticket to the top of their list every
    time.

    The other half of the rule is that a real interruption does put the next
    pick-up back on the record, and the two tests at the end are what keep
    this from being solved by never saying it twice.
    """

    def announcements(self, ticket):
        return ticket.messages.filter(
            body=system_messages.TICKET_NOW_HANDLED
        ).count()

    def test_the_first_pick_up_is_announced(self):
        ticket = self.make_ticket()

        lifecycle.claim(ticket=ticket, actor=self.agent)

        self.assertEqual(self.announcements(ticket), 1)

    def test_taking_a_released_ticket_back_does_not_say_it_again(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=None)

        lifecycle.claim(ticket=ticket, actor=self.agent)

        self.assertEqual(self.announcements(ticket), 1)

    def test_the_owner_dropdown_cannot_stack_the_sentence_up(self):
        """Five rounds of release and take back, still one line."""
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        for _ in range(5):
            lifecycle.assign(ticket=ticket, actor=self.agent, assignee=None)
            lifecycle.claim(ticket=ticket, actor=self.agent)

        self.assertEqual(self.announcements(ticket), 1)

    def test_a_silent_pick_up_leaves_the_requesters_clock_alone(self):
        """Nothing was added to their timeline, so nothing orders their list
        differently."""
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=None)
        ticket.refresh_from_db()
        updated_before = ticket.updated_at

        lifecycle.claim(ticket=ticket, actor=self.agent)

        ticket.refresh_from_db()
        self.assertEqual(ticket.updated_at, updated_before)

    def test_a_silent_pick_up_still_moves_the_status(self):
        """The sentence is what is skipped, not the state change."""
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=None)

        lifecycle.claim(ticket=ticket, actor=self.agent)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.assertEqual(ticket.assignee_id, self.agent.pk)

    def test_a_reopened_ticket_is_announced_again(self):
        """The requester's reply put REOPENED on the timeline after the old
        announcement, so the ticket really did stop being handled and they
        were told so."""
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="Still stuck, sorry."
        )

        lifecycle.claim(ticket=ticket, actor=self.agent)

        self.assertEqual(self.announcements(ticket), 2)

    def test_a_status_an_agent_corrected_by_hand_is_announced_again(self):
        """The door beside the reopen: no requester reply anywhere in it.

        Resolving by mistake and putting the status back writes its own two
        lines, so the next pick-up is news again.
        """
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.OPEN, actor=self.agent
        )

        lifecycle.assign(
            ticket=ticket, actor=self.agent, assignee=self.other_agent
        )

        self.assertEqual(self.announcements(ticket), 2)


class AnOwnerlessInProgressTicketCanBePutRightTests(LifecycleTestCase):
    """Releasing is how the queue is meant to get out of "in progress with
    nobody on it", and it has to work on the tickets that arrive in that state
    by another road.

    ``Ticket.assignee`` is SET_NULL, so deleting an agent's account empties
    the owner without touching the status. Refusing the release because the
    owner is already what was asked for left the ticket unfixable from the
    owner control it belongs to.
    """

    def orphan(self):
        """What SET_NULL leaves behind when an agent's account goes."""
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        Ticket.objects.filter(pk=ticket.pk).update(assignee=None)
        ticket.refresh_from_db()
        return ticket

    def test_choosing_unassigned_releases_an_ownerless_in_progress_ticket(self):
        ticket = self.orphan()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)

        lifecycle.assign(ticket=ticket, actor=self.other_agent, assignee=None)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertIsNone(ticket.assignee_id)

    def test_the_repair_says_nothing_to_the_requester(self):
        ticket = self.orphan()
        messages_before = ticket.messages.count()
        updated_before = ticket.updated_at

        lifecycle.assign(ticket=ticket, actor=self.other_agent, assignee=None)

        ticket.refresh_from_db()
        self.assertEqual(ticket.messages.count(), messages_before)
        self.assertEqual(ticket.updated_at, updated_before)

    def test_a_second_click_on_unassigned_still_records_nothing(self):
        """The exception is for the broken state only. Once the ticket is
        open, choosing Unassigned again is the ordinary no-op."""
        ticket = self.orphan()
        lifecycle.assign(ticket=ticket, actor=self.other_agent, assignee=None)
        rows_before = AuditLog.objects.filter(
            entity_type="ticket", entity_id=ticket.pk, action="assign"
        ).count()

        lifecycle.assign(ticket=ticket, actor=self.other_agent, assignee=None)

        self.assertEqual(
            AuditLog.objects.filter(
                entity_type="ticket", entity_id=ticket.pk, action="assign"
            ).count(),
            rows_before,
        )


class AScreeningTicketCanBeParkedOffTheClockTests(LifecycleTestCase):
    """A known gap, recorded here rather than left to be rediscovered.

    A screening ticket has no requester. Replying to one and moving it to
    "pending user" in the same action parks it in a status that says we are
    waiting on a person who does not exist, and "pending user" is one of the
    two statuses the overdue clock does not run in. Nothing the product does
    on its own takes it out again: the requester who would normally reply and
    restart the clock is not there.

    Stopping the clock by answering is intended and is written down as such
    in handoff.py. Landing in a status that names a requester who does not
    exist is not. The block belongs where the agent is told the reply has
    nobody to go to, which is the admin detail panel and its view, so this
    test pins the behaviour rather than changing it. If somebody closes the
    gap, this test is the one that should be rewritten with it.
    """

    def screening_ticket(self):
        sender = SimpleNamespace(country=None)
        message = SimpleNamespace(
            pk=42,
            group=SimpleNamespace(pk=7, group_name="Team Photosynthesis"),
            sender_user=sender,
        )
        verdict = SimpleNamespace(
            flagged=True, layer="rule", category="bullying", reason="name calling"
        )
        return create_ticket_from_screening(message, verdict, "you are useless")

    def test_replying_and_parking_it_leaves_a_clock_nothing_restarts(self):
        ticket = self.screening_ticket()
        self.assertIsNone(ticket.created_by_id)

        lifecycle.add_support_reply(
            ticket=ticket,
            actor=self.agent,
            body="Looked at it, following up in the group.",
            move_to_pending=True,
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        self.assertIsNone(ticket.awaiting_support_since)

    def test_it_never_goes_red_however_long_it_sits_there(self):
        """Measured against a time this test names, not against the clock of
        whichever machine runs it."""
        ticket = self.screening_ticket()
        lifecycle.add_support_reply(
            ticket=ticket,
            actor=self.agent,
            body="Looked at it, following up in the group.",
            move_to_pending=True,
        )
        ticket.refresh_from_db()

        a_year_later = ticket.support_updated_at + timedelta(days=365)

        self.assertEqual(queue.overdue_ids([ticket], now=a_year_later), set())

    def test_an_agent_moving_it_back_is_what_restarts_it(self):
        """The only way out, and the reason this is a gap rather than a
        permanent loss."""
        ticket = self.screening_ticket()
        lifecycle.add_support_reply(
            ticket=ticket,
            actor=self.agent,
            body="Looked at it, following up in the group.",
            move_to_pending=True,
        )

        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.IN_PROGRESS, actor=self.agent
        )

        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.awaiting_support_since)


class BulkAssignFailureReasonsTests(LifecycleTestCase):
    """What the queue page prints beside a ticket it could not assign.

    Two ways to fail, and they are not interchangeable: the page tells the
    agent that re-sending the batch will not help only when every failure is
    "not found", so anything that can come good on a second try has to read
    differently.
    """

    def test_a_row_deleted_before_the_lock_reads_the_same_as_one_already_gone(self):
        """The race the pre-read cannot close, and the reason string it wrote.

        bulk_assign reads the ticket, then locks it, and an admin can delete
        it in between. That second branch used to append the exception text,
        and TicketGone spells the database id: the agent saw
        "SUP-2026-00001 (Ticket 7 was deleted.)" beside a ticket whose number
        is the only identifier anything on that screen prints.

        Driven through _lock rather than through two threads, so it lands the
        same way on SQLite and on PostgreSQL and does not depend on timing.
        """
        ticket = self.make_ticket()
        real_lock = lifecycle._lock

        def delete_then_lock(target):
            Ticket.objects.filter(pk=target.pk).update(deleted_at=timezone.now())
            return real_lock(target)

        with patch.object(lifecycle, "_lock", side_effect=delete_then_lock):
            results = lifecycle.bulk_assign(
                ticket_ids=[ticket.pk], assignee=self.other_agent, actor=self.agent,
            )

        self.assertEqual(
            results,
            [{"ticketId": ticket.pk, "ok": False, "error": "not found"}],
        )

    def test_no_failure_reason_carries_a_database_id(self):
        """The property, not the one string that broke it.

        A reason is printed next to the ticket number the agent selected. Any
        number in it is a second identifier for the same ticket that nothing
        on the queue prints, so the reader has nothing to match it against.
        """
        ticket = self.make_ticket()
        real_lock = lifecycle._lock

        def delete_then_lock(target):
            Ticket.objects.filter(pk=target.pk).update(deleted_at=timezone.now())
            return real_lock(target)

        with patch.object(lifecycle, "_lock", side_effect=delete_then_lock):
            results = lifecycle.bulk_assign(
                ticket_ids=[ticket.pk], assignee=self.other_agent, actor=self.agent,
            )

        for row in results:
            reason = row.get("error", "")
            self.assertNotIn(
                str(ticket.pk), reason,
                f"the failure reason names the database id: {reason!r}",
            )

    def test_an_unexpected_failure_still_reports_its_own_reason(self):
        """The other branch, which the page treats as worth retrying.

        Folding everything into "not found" would tell the agent to give up on
        a batch that a second attempt would put through.
        """
        ticket = self.make_ticket()
        with patch.object(
            lifecycle, "_assign_one", side_effect=IntegrityError("database is locked")
        ):
            results = lifecycle.bulk_assign(
                ticket_ids=[ticket.pk], assignee=self.other_agent, actor=self.agent,
            )

        self.assertEqual(
            results,
            [{"ticketId": ticket.pk, "ok": False, "error": "database is locked"}],
        )
