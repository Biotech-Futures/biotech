import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from datetime import timezone as dt_timezone

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APITestCase

from unittest import skipIf
from unittest.mock import patch

import json

from apps.audit.models import AuditLog
from apps.common.storage import reset_managed_storage_caches
from apps.groups.models import Countries
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from apps.tickets.services import lifecycle
from apps.tickets.services.attachments import stored_attachments
from apps.users.models import AdminScope

User = get_user_model()

QUEUE = "/api/v1/admin/tickets/"
_MEDIA = tempfile.mkdtemp(prefix="ticket-admin-tests-")


def pdf(name="note.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4" + b"0" * 128, content_type="application/pdf")


@override_settings(MEDIA_ROOT=_MEDIA)
class AdminTicketAPITestCase(APITestCase):
    def setUp(self):
        reset_managed_storage_caches()
        # Posting a message is rate-limited per person, and the counter lives
        # in the cache, which outlives the per-test transaction rollback that
        # recycles user ids. Clear it so test order cannot make one of these
        # fail. Safe here only because settings_test pins CACHES to locmem.
        cache.clear()
        self.australia = Countries.objects.create(country_name="Australia")
        self.brazil = Countries.objects.create(country_name="Brazil")

        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson", country=self.australia,
        )
        self.other_requester = User.objects.create_user(
            email="bruno@example.com", password="pass1234",
            first_name="Bruno", last_name="Silva", country=self.brazil,
        )
        # A support agent who is not an admin — the case the whole role exists
        # for.
        self.agent = User.objects.create_user(
            email="agent@example.com", password="pass1234",
            first_name="Sam", last_name="Reid",
        )
        SupportScope.objects.create(user=self.agent)
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pass1234",
            first_name="Ada", last_name="Lin",
        )
        AdminScope.objects.create(user=self.admin)
        self.outsider = User.objects.create_user(
            email="nobody@example.com", password="pass1234",
            first_name="Nia", last_name="Bell",
        )
        self.client.force_login(self.agent)

    def tearDown(self):
        reset_managed_storage_caches()

    def make_ticket(self, owner=None, subject="Cannot access group workspace", **fields):
        ticket = lifecycle.create_ticket(
            user=owner or self.requester,
            category=fields.pop("category", TicketCategory.HELP_STUDENT_GROUP),
            subject=subject,
            body="I get an error opening my group.",
        )
        if fields:
            Ticket.objects.filter(pk=ticket.pk).update(**fields)
            ticket.refresh_from_db()
        return ticket

    def queue_order(self):
        """Ticket ids as the support queue orders them, newest activity first."""
        return [row["id"] for row in self.client.get(QUEUE).json()["data"]["items"]]


class QueueAccessTests(AdminTicketAPITestCase):
    def test_a_support_agent_who_is_not_an_admin_can_work_the_queue(self):
        self.assertEqual(self.client.get(QUEUE).status_code, status.HTTP_200_OK)

    def test_an_admin_can_work_the_queue_without_a_support_row(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(QUEUE).status_code, status.HTTP_200_OK)

    def test_an_ordinary_user_is_refused(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(QUEUE).status_code, status.HTTP_403_FORBIDDEN)

    def test_the_support_agent_is_still_shut_out_of_the_rest_of_the_admin_area(self):
        # Nothing was changed to achieve this: every other admin endpoint is
        # already gated on AdminScope, which the agent does not have.
        response = self.client.get("/api/v1/admin/user/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_granting_support_access_is_admins_only(self):
        response = self.client.post(f"{QUEUE}support-scope/", {"userId": self.outsider.pk})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@skipIf(
    connection.vendor == "sqlite",
    "Tied-row order is stable on SQLite, so this would pass without testing "
    "anything. Runs against local Postgres (--settings=config.settings_local).",
)
class QueueOrderingIsTotalTests(AdminTicketAPITestCase):
    """The queue's sort key has to put tied rows in a defined order.

    "-support_updated_at" on its own does not. Rows sharing a timestamp can
    come back in a different sequence on each query, and OFFSET paging issues
    one query per page, so a ticket can sit past the offset on every page and
    never be shown. Measured on real Postgres: 60 tickets on one timestamp,
    six pages, 40 distinct tickets seen and 20 never returned at all. The
    agent sees a full page count and no hint that anything is missing.

    ⚠️ Postgres only, and skipped rather than passed elsewhere. Measured on
    SQLite the queryset returns the same sequence with and without the
    tiebreaker, so removing it there is an equivalent mutation. Letting this
    report PASS on SQLite was worse than not having it: CI runs
    ``--settings=config.settings_test`` and no workflow starts a Postgres
    service, so the green tick claimed cover that did not exist. A skip says
    so. Verify changes here with --settings=config.settings_local.
    """

    def tied_tickets(self, count):
        """Rows written straight to the table: 60 trips through create_ticket
        would allocate 60 numbers and queue 60 emails to prove nothing extra.
        """
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
            for i in range(count)
        ])
        return list(
            Ticket.objects.filter(subject__startswith="Tied ")
            .values_list("pk", flat=True)
        )

    def test_paging_through_tied_tickets_shows_each_one_exactly_once(self):
        # 60 over six pages is the size that reproduced it on Postgres; the
        # planner is free to be stable on a handful of rows.
        expected = self.tied_tickets(60)

        seen, page = [], 1
        while True:
            data = self.client.get(QUEUE, {"page": page, "limit": 10}).json()["data"]
            seen.extend(row["id"] for row in data["items"])
            if not data["hasMore"]:
                break
            page += 1

        self.assertEqual(len(seen), len(set(seen)), "a ticket appeared on two pages")
        self.assertEqual(
            set(seen), set(expected),
            f"{len(set(expected) - set(seen))} tickets never appeared on any page",
        )


class QueueRowTests(AdminTicketAPITestCase):
    def test_the_row_reports_the_support_clock_not_the_requesters(self):
        ticket = self.make_ticket()
        lifecycle.add_internal_note(ticket=ticket, actor=self.agent, body="Internal.")
        ticket.refresh_from_db()

        # The internal note moved only the support clock, so the two now
        # differ — but by microseconds. Comparing at second precision would
        # make them equal and the assertion would hold either way.
        self.assertNotEqual(ticket.updated_at, ticket.support_updated_at)

        row = self.client.get(QUEUE).json()["data"]["items"][0]
        reported = parse_datetime(row["supportUpdatedAt"])
        self.assertEqual(reported, ticket.support_updated_at)
        self.assertNotEqual(reported, ticket.updated_at)
        self.assertNotIn("lastUpdated", row)

    def test_a_screening_raised_ticket_is_not_labelled_anonymous(self):
        # created_by is null on those, and a naive "no requester means
        # anonymous" would mislabel every one of them.
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(created_by=None, channel="ai_screening")

        row = self.client.get(QUEUE).json()["data"]["items"][0]
        self.assertFalse(row["user"]["anonymous"])

    def test_the_queue_is_sorted_by_most_recent_support_activity(self):
        older = self.make_ticket(subject="Older")
        self.make_ticket(subject="Newer")
        lifecycle.add_internal_note(ticket=older, actor=self.agent, body="Bumping.")

        items = self.client.get(QUEUE).json()["data"]["items"]
        self.assertEqual(items[0]["id"], older.pk)

    def test_a_soft_deleted_ticket_leaves_the_queue(self):
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(deleted_at=timezone.now())

        data = self.client.get(QUEUE).json()["data"]
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["items"], [])


class QueueFilterTests(AdminTicketAPITestCase):
    def setUp(self):
        super().setUp()
        self.au = self.make_ticket(subject="Australian one")
        self.br = self.make_ticket(owner=self.other_requester, subject="Brazilian one")
        self.unknown = self.make_ticket(subject="No region on file", region="")
        Ticket.objects.filter(pk=self.au.pk).update(region="Australia")
        Ticket.objects.filter(pk=self.br.pk).update(region="Brazil")

    def ids_for(self, **params):
        return {row["id"] for row in self.client.get(QUEUE, params).json()["data"]["items"]}

    def test_filtering_by_region(self):
        self.assertEqual(self.ids_for(region="Brazil"), {self.br.pk})

    def test_the_unknown_region_bucket_is_selectable(self):
        # Without a sentinel this bucket has a name in the dropdown but an
        # empty value, and an empty query parameter reads as "no filter".
        self.assertEqual(self.ids_for(region="__unknown__"), {self.unknown.pk})

    def test_a_non_numeric_assignee_filter_is_rejected_not_a_500(self):
        # assignee is the only filter that lands on an FK id. Django coerces
        # it while building the query, so a non-number raises ValueError deep
        # in the ORM and the platform handler turns that into a 500.
        response = self.client.get(QUEUE, {"assignee": "abc"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filtering_by_status(self):
        lifecycle.claim(ticket=self.au, actor=self.agent)
        self.assertEqual(self.ids_for(status="in_progress"), {self.au.pk})

    def test_filtering_by_category(self):
        Ticket.objects.filter(pk=self.br.pk).update(category=TicketCategory.ACCOUNT_ACCESS)
        self.assertEqual(self.ids_for(category="account_access"), {self.br.pk})

    def test_filtering_by_priority(self):
        Ticket.objects.filter(pk=self.au.pk).update(priority=TicketPriority.HIGH)
        self.assertEqual(self.ids_for(priority="high"), {self.au.pk})

    def test_filtering_by_assignee(self):
        lifecycle.claim(ticket=self.br, actor=self.agent)
        self.assertEqual(self.ids_for(assignee=self.agent.pk), {self.br.pk})

    def test_filters_combine(self):
        Ticket.objects.filter(pk=self.au.pk).update(priority=TicketPriority.HIGH)
        self.assertEqual(self.ids_for(region="Australia", priority="high"), {self.au.pk})
        self.assertEqual(self.ids_for(region="Brazil", priority="high"), set())

    def test_search_finds_a_ticket_by_its_number(self):
        self.assertEqual(self.ids_for(search=self.br.ticket_number), {self.br.pk})

    def test_search_finds_a_ticket_by_its_subject(self):
        self.assertEqual(self.ids_for(search="Brazilian"), {self.br.pk})

    def test_search_finds_a_ticket_by_the_requesters_name(self):
        self.assertEqual(self.ids_for(search="Bruno"), {self.br.pk})

    def test_search_finds_a_ticket_by_the_requesters_email(self):
        self.assertEqual(self.ids_for(search="bruno@example.com"), {self.br.pk})

    def test_search_does_not_reach_soft_deleted_tickets(self):
        Ticket.objects.filter(pk=self.br.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.ids_for(search="Brazilian"), set())


@override_settings(
    MEDIA_ROOT=_MEDIA,
    TICKET_SLA_HIGH_HOURS=4,
    TICKET_SLA_NORMAL_HOURS=24,
    TICKET_SLA_LOW_HOURS=72,
)
class QueueFloatTests(AdminTicketAPITestCase):
    """A reply from the requester has to reach the support queue's sort key.

    There are two clocks (DEC-016①): ``updated_at`` is the requester's and
    ``support_updated_at`` is what the queue orders by. Advancing one and
    forgetting the other is the failure this module is most exposed to, and
    until now nothing tested it — rolling the support clock back after every
    user reply left the whole suite green.
    """

    def test_a_requester_reply_floats_the_ticket_to_the_top_of_the_queue(self):
        older = self.make_ticket(subject="Raised first")
        newer = self.make_ticket(subject="Raised second")
        self.assertEqual(self.queue_order()[0], newer.pk, "precondition")

        lifecycle.add_user_reply(
            ticket=older, user=self.requester, body="Any update on this?",
        )

        self.assertEqual(
            self.queue_order()[0],
            older.pk,
            "the requester replied and the queue did not notice",
        )

    def test_an_internal_action_does_not_move_the_requesters_clock(self):
        """The other direction of the same rule.

        A hand-off is none of the requester's business, so it must move the
        queue's clock without floating the ticket in the requester's own list.
        """
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        seen_by_requester = ticket.updated_at

        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.admin)

        ticket.refresh_from_db()
        self.assertEqual(ticket.updated_at, seen_by_requester)
        self.assertGreater(ticket.support_updated_at, seen_by_requester)


class OverdueTests(AdminTicketAPITestCase):
    def aged(self, *, hours, priority=TicketPriority.HIGH, **fields):
        """A ticket that has been sitting with support for `hours`.

        Both clocks move, and that is the point of the helper. `created_at` is
        what the ticket looks like; `awaiting_support_since` is what the
        Overdue rule actually reads. Before 2026-09-04 they were the same
        question, because the rule was "never answered, and old" — measured
        from creation. It is now "the ball has been with support this long",
        so a helper that only aged `created_at` would leave every ticket here
        looking freshly landed and every assertion below passing vacuously.
        """
        ticket = self.make_ticket(priority=priority, **fields)
        started = timezone.now() - timedelta(hours=hours)
        Ticket.objects.filter(pk=ticket.pk).update(
            created_at=started, awaiting_support_since=started
        )
        ticket.refresh_from_db()
        return ticket

    def overdue_count(self):
        return self.client.get(f"{QUEUE}summary/").json()["data"]["overdue"]

    def test_a_brand_new_ticket_is_already_on_the_clock(self):
        """The client's step one is "Raised" — the clock starts there, with
        nobody having done anything.

        Asserted on a ticket made the ordinary way, with nothing written to
        the column by hand. Every other test here goes through `aged()`, which
        sets the anchor itself, so without this one the whole feature would
        still pass with create_ticket never setting it at all.
        """
        ticket = self.make_ticket()
        self.assertIsNotNone(ticket.awaiting_support_since)

    def test_an_untouched_ticket_goes_overdue_with_nobody_setting_the_column(self):
        """The same gap, seen through the rule rather than the column. Only
        `created_at` is moved here, exactly as it would be by the passage of
        real time; the anchor has to have been written at submission."""
        ticket = self.make_ticket(priority=TicketPriority.HIGH)
        self.assertEqual(self.overdue_count(), 0)

        Ticket.objects.filter(pk=ticket.pk).update(
            created_at=timezone.now() - timedelta(hours=5)
        )
        ticket.refresh_from_db()
        Ticket.objects.filter(pk=ticket.pk).update(
            awaiting_support_since=ticket.awaiting_support_since - timedelta(hours=5)
        )
        self.assertEqual(self.overdue_count(), 1)

    def test_a_high_priority_ticket_is_not_overdue_just_before_its_deadline(self):
        self.aged(hours=3, priority=TicketPriority.HIGH)
        self.assertEqual(self.overdue_count(), 0)

    def test_a_high_priority_ticket_is_overdue_just_after_its_deadline(self):
        self.aged(hours=5, priority=TicketPriority.HIGH)
        self.assertEqual(self.overdue_count(), 1)

    def test_each_priority_has_its_own_deadline(self):
        self.aged(hours=5, priority=TicketPriority.NORMAL)   # 24h allowed
        self.aged(hours=30, priority=TicketPriority.LOW)     # 72h allowed
        self.assertEqual(self.overdue_count(), 0)

    def test_an_ordinary_support_reply_stops_the_clock(self):
        """move_to_pending defaults to False, and this is the default path — a
        plain Reply. It is also the mutation detector for the one mistake this
        feature invites: the clear has to be its own keyword on _touch, not an
        entry in the `moved` dict, because that dict is only populated on the
        move-to-pending branch. Put it in `moved` and every ordinary reply
        leaves the ticket on the clock forever."""
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="On it.")
        self.assertEqual(self.overdue_count(), 0)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.awaiting_support_since)

    def test_a_reply_the_requester_has_since_answered_goes_overdue_again(self):
        """The client's loop, end to end: raised, answered, answered back, and
        then support sits on it. Under the old first-response rule this was
        impossible — one reply made a ticket permanently safe."""
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="On it.")
        self.assertEqual(self.overdue_count(), 0)

        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="That did not work."
        )
        # Fresh: they have only just replied.
        self.assertEqual(self.overdue_count(), 0)

        ticket.refresh_from_db()
        Ticket.objects.filter(pk=ticket.pk).update(
            awaiting_support_since=timezone.now() - timedelta(hours=5)
        )
        self.assertEqual(self.overdue_count(), 1)

    def test_the_clock_is_not_restarted_by_the_requester_chasing_us(self):
        """Somebody who writes three times in a row has been waiting since the
        first message. Restarting on each would hand support a fresh window
        every time the person asks whether anyone is there."""
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="On it.")
        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="Still stuck."
        )
        ticket.refresh_from_db()
        first = ticket.awaiting_support_since
        Ticket.objects.filter(pk=ticket.pk).update(
            awaiting_support_since=timezone.now() - timedelta(hours=5)
        )

        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="Anyone there?"
        )

        ticket.refresh_from_db()
        self.assertLess(ticket.awaiting_support_since, timezone.now() - timedelta(hours=4))
        self.assertIsNotNone(first)
        self.assertEqual(self.overdue_count(), 1)

    def test_an_internal_note_does_not_stop_the_clock(self):
        """A note is invisible to the requester, so nobody has been answered.
        An agent who investigates for six hours and writes notes is still
        somebody the requester is waiting on."""
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.add_internal_note(
            ticket=ticket, actor=self.agent, body="Checked the logs, nothing yet."
        )
        self.assertEqual(self.overdue_count(), 1)

    def test_claiming_a_ticket_does_not_stop_the_clock(self):
        """Otherwise an agent could make the red number go down by claiming
        tickets, which is the opposite of what the number is for."""
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.claim(ticket=ticket, actor=self.agent)
        self.assertEqual(self.overdue_count(), 1)

    def test_a_ticket_waiting_on_the_requester_is_never_overdue(self):
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.mark_pending(ticket=ticket, actor=self.agent)
        self.assertEqual(self.overdue_count(), 0)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.awaiting_support_since)

    def test_moving_a_ticket_off_pending_user_puts_it_back_on_the_clock(self):
        """The dead zone. A requester answers some other way — rings up,
        catches someone at a workshop — and an agent corrects the status by
        hand. Nothing else on that path sets the anchor, so without it the
        ticket sits with support, ageing, and can never go red: the one-shot
        behaviour the client rejected, arriving through a different door."""
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.mark_pending(ticket=ticket, actor=self.agent)
        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.IN_PROGRESS, actor=self.agent
        )

        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.awaiting_support_since)

        Ticket.objects.filter(pk=ticket.pk).update(
            awaiting_support_since=timezone.now() - timedelta(hours=5)
        )
        self.assertEqual(self.overdue_count(), 1)

    def test_a_status_change_after_an_answer_does_not_restart_the_clock(self):
        """An agent answers, then tidies the status from the dropdown.

        The requester has said nothing, so the ball is not with support and
        the ticket must stay off the clock. The first version of set_status
        re-armed on any change that was not into "pending user", so this
        ordinary tidy-up put an answered ticket back on the clock and it went
        red four hours later on its own.
        """
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Done.")
        ticket.refresh_from_db()
        self.assertIsNone(ticket.awaiting_support_since)

        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.IN_PROGRESS, actor=self.agent
        )

        ticket.refresh_from_db()
        self.assertIsNone(ticket.awaiting_support_since)
        self.assertEqual(self.overdue_count(), 0)

    def test_a_status_change_while_still_waiting_keeps_the_original_start(self):
        """The other half: a ticket nobody has answered stays on the clock it
        was already running, rather than getting a fresh window because an
        agent moved it from Open to In progress."""
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        started = ticket.awaiting_support_since

        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.IN_PROGRESS, actor=self.agent
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.awaiting_support_since, started)
        self.assertEqual(self.overdue_count(), 1)

    def test_un_resolving_from_the_dropdown_puts_it_back_on_the_clock(self):
        """An agent resolves by mistake and corrects it from the dropdown.

        The second door into the same defect, and it was opened by the fix for
        the first one. resolve() clears the anchor; a set_status that only
        re-armed when leaving "pending user" left this ticket in progress,
        sitting with support, and structurally unable ever to go red.

        Not the same path as reopen(): that one is the requester replying, and
        it sets the anchor itself.
        """
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.awaiting_support_since)

        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.IN_PROGRESS, actor=self.agent
        )

        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.awaiting_support_since)
        Ticket.objects.filter(pk=ticket.pk).update(
            awaiting_support_since=timezone.now() - timedelta(hours=5)
        )
        self.assertEqual(self.overdue_count(), 1)

    def test_no_route_out_of_an_off_clock_state_leaves_a_ticket_unwatchable(self):
        """The invariant behind both mistakes, checked over every route rather
        than over the two somebody thought to write a case for.

        A ticket that is with support and has a null anchor can never be
        counted overdue, whatever happens to it afterwards. So: from each state
        where support is off the clock, into each state where it is on, by
        every transition an agent can drive.
        """
        for before in (TicketStatus.PENDING_USER, TicketStatus.RESOLVED):
            for after in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS):
                with self.subTest(route=f"{before} -> {after}"):
                    ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
                    lifecycle.set_status(
                        ticket=ticket, new_status=before, actor=self.agent
                    )
                    ticket.refresh_from_db()
                    self.assertIsNone(
                        ticket.awaiting_support_since,
                        f"{before} must take the ticket off the clock",
                    )

                    lifecycle.set_status(
                        ticket=ticket, new_status=after, actor=self.agent
                    )

                    ticket.refresh_from_db()
                    self.assertIsNotNone(
                        ticket.awaiting_support_since,
                        f"a ticket moved {before} -> {after} is with support "
                        "again and must be able to go overdue",
                    )

    def test_reopening_puts_a_ticket_back_on_the_clock(self):
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.awaiting_support_since)

        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="It is back."
        )
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.awaiting_support_since)

    def test_a_resolved_ticket_is_never_overdue(self):
        ticket = self.aged(hours=48, priority=TicketPriority.HIGH)
        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.RESOLVED, actor=self.agent
        )
        self.assertEqual(self.overdue_count(), 0)

    def test_the_queue_row_carries_the_same_verdict_as_the_counter(self):
        self.aged(hours=5, priority=TicketPriority.HIGH)
        row = self.client.get(QUEUE).json()["data"]["items"][0]
        self.assertTrue(row["overdue"])


class SummaryTests(AdminTicketAPITestCase):
    def test_the_four_counters_match_a_hand_count(self):
        self.make_ticket(subject="Untouched and open")
        claimed = self.make_ticket(subject="Being worked on")
        lifecycle.claim(ticket=claimed, actor=self.agent)
        waiting = self.make_ticket(subject="Waiting on the requester")
        lifecycle.claim(ticket=waiting, actor=self.agent)
        lifecycle.mark_pending(ticket=waiting, actor=self.agent)
        done = self.make_ticket(subject="Finished")
        lifecycle.resolve(ticket=done, actor=self.agent)

        data = self.client.get(f"{QUEUE}summary/").json()["data"]
        self.assertEqual(data["open"], 1)
        self.assertEqual(data["pendingUser"], 1)
        # Unassigned counts only tickets still needing work: the resolved one
        # has no owner either, but nobody has to pick it up.
        self.assertEqual(data["unassigned"], 1)
        self.assertEqual(data["overdue"], 0)


class PatchTests(AdminTicketAPITestCase):
    def test_status_and_assignee_together_are_rejected(self):
        ticket = self.make_ticket()
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"status": "in_progress", "assignee": self.agent.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_priority_may_accompany_a_status_change(self):
        ticket = self.make_ticket()
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"status": "pending_user", "priority": "high"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        self.assertEqual(ticket.priority, TicketPriority.HIGH)

    def test_changing_the_priority_moves_no_clock_the_requester_can_see(self):
        """The requester picks the priority and can read it on their ticket.
        The *change* is still quiet: an agent re-triaging is a decision, not a
        message, so it writes no timeline entry and does not float the ticket
        to the top of the requester's list."""
        ticket = self.make_ticket()
        before_user, before_support = ticket.updated_at, ticket.support_updated_at
        messages_before = ticket.messages.count()

        self.client.patch(f"{QUEUE}{ticket.pk}/", {"priority": "high"}, format="json")

        ticket.refresh_from_db()
        self.assertEqual(ticket.updated_at, before_user)
        self.assertGreater(ticket.support_updated_at, before_support)
        self.assertEqual(ticket.messages.count(), messages_before)

    def test_support_can_refile_a_ticket_into_another_category(self):
        """The client's eight categories include near-synonyms, so agents will
        routinely need to correct one. Before 2026-09-04 nothing in any
        interface could."""
        ticket = self.make_ticket()
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"category": TicketCategory.TECHNICAL_ISSUE},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.category, TicketCategory.TECHNICAL_ISSUE)
        self.assertEqual(
            response.data["data"]["category"], TicketCategory.TECHNICAL_ISSUE
        )

    def test_a_category_change_on_its_own_is_a_valid_request(self):
        """The serializer refuses an empty body, and category has to count as
        content or the only way to re-file would be to change something else
        at the same time."""
        ticket = self.make_ticket()
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"category": TicketCategory.OTHER},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refiling_writes_an_audit_row(self):
        ticket = self.make_ticket(category=TicketCategory.ACCOUNT_ACCESS)
        self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"category": TicketCategory.REGISTRATION},
            format="json",
        )
        row = AuditLog.objects.filter(
            entity_type=lifecycle.AUDIT_ENTITY_TYPE,
            entity_id=ticket.pk,
            action="category",
        ).latest("created_at")
        self.assertEqual(row.before_state, {"category": "account_access"})
        self.assertEqual(row.after_state, {"category": "registration"})

    def test_refiling_to_the_same_category_writes_no_audit_row(self):
        ticket = self.make_ticket(category=TicketCategory.ACCOUNT_ACCESS)
        self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"category": TicketCategory.ACCOUNT_ACCESS},
            format="json",
        )
        self.assertFalse(
            AuditLog.objects.filter(
                entity_type=lifecycle.AUDIT_ENTITY_TYPE,
                entity_id=ticket.pk,
                action="category",
            ).exists()
        )

    def test_refiling_moves_the_support_clock_and_not_the_requesters(self):
        """Re-filing is triage, not a message. The requester can see the new
        value if they look, but their list must not reorder and nothing lands
        in their timeline: the ticket did not change, only our filing of it."""
        ticket = self.make_ticket(category=TicketCategory.ACCOUNT_ACCESS)
        before_user, before_support = ticket.updated_at, ticket.support_updated_at
        messages_before = ticket.messages.count()

        self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"category": TicketCategory.HELP_MENTOR},
            format="json",
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.updated_at, before_user)
        self.assertGreater(ticket.support_updated_at, before_support)
        self.assertEqual(ticket.messages.count(), messages_before)

    def test_support_may_refile_a_screening_ticket_out_of_flagged_content(self):
        """The internal category is offered on the support side precisely
        because a mis-screened ticket needs a way out of it."""
        ticket = self.make_ticket(category=TicketCategory.FLAGGED_CONTENT)
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"category": TicketCategory.GENERAL_QUESTION},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.category, TicketCategory.GENERAL_QUESTION)

    def test_a_category_the_model_does_not_know_is_refused(self):
        ticket = self.make_ticket()
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            {"category": "programs_groups"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_handing_a_started_ticket_over_is_invisible_to_the_requester(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        before_user = ticket.updated_at
        messages_before = ticket.messages.count()

        self.client.patch(f"{QUEUE}{ticket.pk}/", {"assignee": self.admin.pk}, format="json")

        ticket.refresh_from_db()
        self.assertEqual(ticket.assignee_id, self.admin.pk)
        self.assertEqual(ticket.updated_at, before_user)
        self.assertEqual(ticket.messages.count(), messages_before)

    def test_an_empty_patch_is_rejected(self):
        ticket = self.make_ticket()
        response = self.client.patch(f"{QUEUE}{ticket.pk}/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_ticket_cannot_be_assigned_to_someone_who_cannot_open_it(self):
        ticket = self.make_ticket()
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/", {"assignee": self.outsider.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class BulkAssignTests(AdminTicketAPITestCase):
    def test_only_the_tickets_waiting_in_the_pool_get_a_timeline_message(self):
        open_ticket = self.make_ticket(subject="In the pool")
        waiting = self.make_ticket(subject="Waiting on the requester")
        lifecycle.claim(ticket=waiting, actor=self.agent)
        lifecycle.mark_pending(ticket=waiting, actor=self.agent)
        waiting_messages_before = waiting.messages.count()
        open_messages_before = open_ticket.messages.count()

        response = self.client.post(
            f"{QUEUE}bulk-assign/",
            {"ticketIds": [open_ticket.pk, waiting.pk], "assigneeId": self.admin.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        open_ticket.refresh_from_db()
        waiting.refresh_from_db()
        self.assertEqual(open_ticket.messages.count(), open_messages_before + 1)
        self.assertEqual(waiting.messages.count(), waiting_messages_before)
        self.assertEqual(waiting.status, TicketStatus.PENDING_USER)

    def test_an_unknown_id_is_reported_without_sinking_the_batch(self):
        ticket = self.make_ticket()
        results = self.client.post(
            f"{QUEUE}bulk-assign/",
            {"ticketIds": [ticket.pk, 999999], "assigneeId": self.admin.pk},
            format="json",
        ).json()["data"]["results"]
        self.assertEqual(
            results,
            [{"ticketId": ticket.pk, "ok": True},
             {"ticketId": 999999, "ok": False, "error": "not found"}],
        )

    def test_a_soft_deleted_ticket_cannot_be_swept_up(self):
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(deleted_at=timezone.now())
        results = self.client.post(
            f"{QUEUE}bulk-assign/",
            {"ticketIds": [ticket.pk], "assigneeId": self.admin.pk},
            format="json",
        ).json()["data"]["results"]
        self.assertEqual(results, [{"ticketId": ticket.pk, "ok": False, "error": "not found"}])


class SupportMessageTests(AdminTicketAPITestCase):
    def test_an_agent_can_reply(self):
        ticket = self.make_ticket()
        response = self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {"messageType": "support_reply", "body": "Looking into it now."},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.first_response_at)

    def test_the_support_view_of_the_timeline_includes_internal_notes(self):
        ticket = self.make_ticket()
        self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {"messageType": "internal_note", "body": "Escalating internally."},
        )
        payload = self.client.get(f"{QUEUE}{ticket.pk}/").json()["data"]
        self.assertIn("internal_note", [m["messageType"] for m in payload["messages"]])

    def test_an_internal_note_does_not_count_as_a_first_response(self):
        ticket = self.make_ticket()
        self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {"messageType": "internal_note", "body": "Internal only."},
        )
        ticket.refresh_from_db()
        self.assertIsNone(ticket.first_response_at)

    def test_the_support_side_can_download_a_file_from_an_internal_note(self):
        ticket = self.make_ticket()
        with stored_attachments([pdf("internal.pdf")]) as rows:
            note = lifecycle.add_internal_note(
                ticket=ticket, actor=self.agent, body="Internal.", attachments=rows
            )
        attachment_id = note.attachments.get().pk

        response = self.client.get(f"{QUEUE}{ticket.pk}/attachments/{attachment_id}/")
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_302_FOUND))


class HistoryTests(AdminTicketAPITestCase):
    def test_the_history_reads_oldest_first(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.admin)
        lifecycle.resolve(ticket=ticket, actor=self.admin)

        rows = self.client.get(f"{QUEUE}{ticket.pk}/history/").json()["data"]
        self.assertEqual([r["action"] for r in rows], ["assign", "assign", "resolve"])
        timestamps = [r["createdAt"] for r in rows]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_the_history_says_who_moved_it_and_between_whom(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.admin)

        handover = self.client.get(f"{QUEUE}{ticket.pk}/history/").json()["data"][-1]
        self.assertEqual(handover["actor"]["id"], self.agent.pk)
        self.assertEqual(handover["beforeState"], {"assignee_id": self.agent.pk})
        self.assertEqual(handover["afterState"], {"assignee_id": self.admin.pk})

    def test_an_agent_who_is_not_an_admin_can_read_it(self):
        # The platform's own audit endpoint is gated on is_staff, which would
        # shut this agent out of the record of their own queue.
        ticket = self.make_ticket()
        self.assertEqual(
            self.client.get(f"{QUEUE}{ticket.pk}/history/").status_code,
            status.HTTP_200_OK,
        )


class RosterTests(AdminTicketAPITestCase):
    def test_the_assignee_list_holds_agents_and_admins_once_each(self):
        SupportScope.objects.create(user=self.admin)  # both rows for one person
        rows = self.client.get(f"{QUEUE}assignees/").json()["data"]
        ids = [row["id"] for row in rows]
        self.assertEqual(sorted(ids), sorted({self.agent.pk, self.admin.pk}))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(row["assignable"] for row in rows))

    def test_a_deactivated_agent_is_not_assignable(self):
        """Deactivating someone does not remove their support scope row.

        The two are independent on this platform, so without the is_active
        filter an agent who left stays in the dropdown, and a ticket handed
        to them leaves both counter cards with nobody working it.
        """
        self.agent.is_active = False
        self.agent.save(update_fields=["is_active"])
        self.client.force_login(self.admin)

        # Still listed, because tickets already in their name have to stay
        # findable — but flagged so the assign dropdown will not offer them.
        rows = self.client.get(f"{QUEUE}assignees/").json()["data"]
        me = [row for row in rows if row["id"] == self.agent.pk]
        self.assertEqual(len(me), 1)
        self.assertFalse(me[0]["assignable"])

        ticket = self.make_ticket()
        refused = self.client.patch(
            f"{QUEUE}{ticket.pk}/", {"assignee": self.agent.pk}, format="json"
        )
        self.assertEqual(refused.status_code, status.HTTP_400_BAD_REQUEST)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.assignee_id)

    def test_a_deactivated_agents_tickets_stay_findable(self):
        """The half that the is_active filter took away and had to give back.

        Switching an account off does not move the tickets already in their
        name. If the filter dropdown drops them at the same time, that work
        becomes invisible in bulk: it is not unassigned, so no counter shows
        it, and there is no value to filter by.
        """
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        self.agent.is_active = False
        self.agent.save(update_fields=["is_active"])
        self.client.force_login(self.admin)

        rows = self.client.get(f"{QUEUE}assignees/").json()["data"]
        row = next((r for r in rows if r["id"] == self.agent.pk), None)
        self.assertIsNotNone(row, "their tickets became unfindable")
        self.assertFalse(row["assignable"])

        found = self.client.get(QUEUE, {"assignee": self.agent.pk}).json()["data"]
        self.assertEqual([t["id"] for t in found["items"]], [ticket.pk])

    def test_a_revoked_agents_tickets_stay_findable(self):
        """The case that actually needs the ``| Q(pk__in=owners)`` clause.

        The test above deactivates the account but leaves the SupportScope row
        in place, so the query still matches them on the scope join and the
        owners clause carries no weight — deleting it left that test green.
        Revoking the row is what removes every other reason for them to be in
        this list, and their tickets are still in their name.
        """
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        SupportScope.objects.filter(user=self.agent).delete()
        self.client.force_login(self.admin)

        rows = self.client.get(f"{QUEUE}assignees/").json()["data"]
        row = next((r for r in rows if r["id"] == self.agent.pk), None)

        self.assertIsNotNone(row, "a revoked agent's tickets became unfindable")
        found = self.client.get(QUEUE, {"assignee": self.agent.pk}).json()["data"]
        self.assertEqual([t["id"] for t in found["items"]], [ticket.pk])

    def test_a_revoked_agent_is_offered_for_filtering_but_not_for_assigning(self):
        """``assignable`` has to agree with what the write path accepts.

        Revoking a support row leaves the account active, so an is_active
        reading of "assignable" kept offering them in the assign dropdown
        while TicketPatchSerializer refused the same person with a 400. The
        agent picked a name the product had just shown them and got an error
        with nothing to explain it.
        """
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        SupportScope.objects.filter(user=self.agent).delete()
        self.client.force_login(self.admin)

        rows = self.client.get(f"{QUEUE}assignees/").json()["data"]
        row = next(r for r in rows if r["id"] == self.agent.pk)
        self.assertFalse(
            row["assignable"],
            "offered as assignable, but the write path rejects them",
        )

        # The other half of the same claim: the write path really does refuse.
        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/", {"assignee": self.agent.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_region_dropdown_ends_with_the_unknown_bucket(self):
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(region="Australia")
        rows = self.client.get(f"{QUEUE}regions/").json()["data"]
        self.assertEqual(rows[-1], {"value": "__unknown__", "label": "Unknown"})
        self.assertIn({"value": "Australia", "label": "Australia"}, rows)

    def test_an_admin_can_grant_and_revoke_support_access(self):
        self.client.force_login(self.admin)
        granted = self.client.post(f"{QUEUE}support-scope/", {"userId": self.outsider.pk})
        self.assertEqual(granted.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SupportScope.objects.filter(user=self.outsider).exists())

        revoked = self.client.delete(f"{QUEUE}support-scope/{self.outsider.pk}/")
        self.assertEqual(revoked.status_code, status.HTTP_200_OK)
        self.assertFalse(SupportScope.objects.filter(user=self.outsider).exists())


class DeleteTests(AdminTicketAPITestCase):
    """Removing a duplicate, a test submission or spam.

    The one action with no undo in the product, so the tests pin who may do
    it and that it leaves a trail.
    """

    def url(self, ticket):
        return f"{QUEUE}{ticket.pk}/delete/"

    def test_an_admin_can_delete_a_ticket(self):
        ticket = self.make_ticket()
        self.client.force_login(self.admin)

        response = self.client.delete(self.url(ticket))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.deleted_at)

    def test_a_deleted_ticket_leaves_the_queue_and_the_counters(self):
        ticket = self.make_ticket()
        self.client.force_login(self.admin)
        before = self.client.get(f"{QUEUE}summary/").json()["data"]["unassigned"]

        self.client.delete(self.url(ticket))

        self.assertEqual(self.queue_order(), [])
        after = self.client.get(f"{QUEUE}summary/").json()["data"]["unassigned"]
        self.assertEqual(after, before - 1)

    def test_a_deleted_ticket_leaves_the_requesters_own_list_too(self):
        """The consequence worth stating out loud (DEC-024, option A).

        The requester-side queryset filters the same column, so deleting is
        not only "hide from the queue" — the student's ticket disappears from
        their Support Centre with no explanation. That is acceptable for a
        duplicate or spam and is why this is admins only.
        """
        ticket = self.make_ticket()
        self.client.force_login(self.admin)
        self.client.delete(self.url(ticket))

        self.client.force_login(self.requester)
        listing = self.client.get("/api/v1/tickets/").json()["data"]
        self.assertEqual(listing["total"], 0)
        detail = self.client.get(f"/api/v1/tickets/{ticket.pk}/")
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_support_agent_who_is_not_an_admin_may_not_delete(self):
        ticket = self.make_ticket()
        self.client.force_login(self.agent)   # SupportScope only, no AdminScope

        response = self.client.delete(self.url(ticket))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.deleted_at)

    def test_deleting_writes_an_audit_row_that_survives_the_ticket(self):
        ticket = self.make_ticket()
        self.client.force_login(self.admin)

        self.client.delete(self.url(ticket))

        row = AuditLog.objects.get(
            entity_type="ticket", entity_id=ticket.pk, action="delete"
        )
        self.assertEqual(row.actor_user_id, self.admin.pk)
        # Enough of the ticket to identify it later without joining to a row
        # that no queryset will return any more.
        self.assertEqual(row.before_state["ticket_number"], ticket.ticket_number)
        self.assertEqual(row.before_state["subject"], ticket.subject)

    def test_a_deleted_ticket_is_404_on_every_admin_write(self):
        """The ordinary case: it was already gone when the request arrived.

        ⚠️ This does NOT exercise the TicketGone translation. `_get_ticket_or_none`
        filters on `live_tickets()`, so a ticket deleted beforehand is refused
        by that lookup and never reaches the service layer. The translation is
        pinned separately below, and the race itself in test_lifecycle.py.
        """
        self.client.force_login(self.admin)
        for label, call in [
            ("status", lambda t: self.client.patch(
                f"{QUEUE}{t.pk}/", {"status": "resolved"}, format="json")),
            ("priority", lambda t: self.client.patch(
                f"{QUEUE}{t.pk}/", {"priority": "high"}, format="json")),
            ("assignee", lambda t: self.client.patch(
                f"{QUEUE}{t.pk}/", {"assignee": self.admin.pk}, format="json")),
            ("reply", lambda t: self.client.post(
                f"{QUEUE}{t.pk}/messages/",
                {"messageType": "support_reply", "body": "hi"})),
            ("internal note", lambda t: self.client.post(
                f"{QUEUE}{t.pk}/messages/",
                {"messageType": "internal_note", "body": "hi"})),
        ]:
            with self.subTest(action=label):
                ticket = self.make_ticket()
                self.client.delete(f"{QUEUE}{ticket.pk}/delete/")
                response = call(ticket)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_404_NOT_FOUND,
                    f"{label} on a deleted ticket answered {response.status_code}",
                )

    def test_a_ticket_deleted_mid_request_answers_404_not_500(self):
        """The translation itself, which the test above cannot reach.

        Deleting between the view's lookup and its write is a real window —
        a reply spends the attachment upload in it. The service layer refuses
        by raising; what must not happen is that refusal reaching the agent as
        a crash. Driven by making the service raise, because producing the
        real interleaving over HTTP is not something a test can time.
        """
        self.client.force_login(self.admin)
        gone = lifecycle.TicketGone("deleted under us")
        for label, target, call in [
            ("status", "set_status", lambda t: self.client.patch(
                f"{QUEUE}{t.pk}/", {"status": "resolved"}, format="json")),
            ("assignee", "assign", lambda t: self.client.patch(
                f"{QUEUE}{t.pk}/", {"assignee": self.admin.pk}, format="json")),
            ("reply", "add_support_reply", lambda t: self.client.post(
                f"{QUEUE}{t.pk}/messages/",
                {"messageType": "support_reply", "body": "hi"})),
            ("internal note", "add_internal_note", lambda t: self.client.post(
                f"{QUEUE}{t.pk}/messages/",
                {"messageType": "internal_note", "body": "hi"})),
        ]:
            with self.subTest(action=label):
                ticket = self.make_ticket()
                with patch.object(lifecycle, target, side_effect=gone):
                    response = call(ticket)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_404_NOT_FOUND,
                    f"{label} surfaced TicketGone as {response.status_code}",
                )

    def test_resolving_a_ticket_deleted_mid_request_answers_404_and_changes_nothing(self):
        """The real interleaving, which the mocked test above cannot reach.

        That test proves the *view* translates TicketGone. It cannot prove the
        service raises one, because it makes the service raise. ``resolve()``
        did not: alone among the write paths it took no row lock and guarded
        with a conditional update, which simply matched nothing on a deleted
        row and returned False. The view never read that return value, so an
        agent resolving a ticket somebody had just deleted got a 200 and
        "Ticket updated successfully" while the ticket stayed open.

        Deleting for real inside the window is the only thing that catches it.
        """
        ticket = self.make_ticket()
        self.client.force_login(self.admin)
        real_set_status = lifecycle.set_status

        def delete_then_call(**kwargs):
            Ticket.objects.filter(pk=ticket.pk).update(deleted_at=timezone.now())
            return real_set_status(**kwargs)

        with patch.object(lifecycle, "set_status", side_effect=delete_then_call):
            response = self.client.patch(
                f"{QUEUE}{ticket.pk}/", {"status": "resolved"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertIsNone(ticket.resolved_at)
        # And no "we're done" email about a ticket the requester cannot open.
        self.assertEqual(mail.outbox, [])

    def test_the_resolve_audit_row_records_the_committed_status(self):
        """``before_status`` has to come from the locked row.

        ``resolve()`` read it off the instance the view handed in, which was
        fetched before the request did anything, so the audit row could name a
        status the ticket had already left. That row is the only record of
        what actually happened.
        """
        ticket = self.make_ticket()
        self.client.force_login(self.admin)
        real_set_status = lifecycle.set_status

        def claim_then_call(**kwargs):
            # Committed by somebody else after the view read the row and
            # before the lock. Doing this *before* the request would prove
            # nothing: the view re-reads on entry, so it would just see the
            # new value and never enter the window this is about.
            Ticket.objects.filter(pk=ticket.pk).update(
                status=TicketStatus.IN_PROGRESS
            )
            return real_set_status(**kwargs)

        with patch.object(lifecycle, "set_status", side_effect=claim_then_call):
            self.client.patch(
                f"{QUEUE}{ticket.pk}/", {"status": "resolved"}, format="json"
            )

        row = AuditLog.objects.get(
            entity_type="ticket", entity_id=ticket.pk, action="resolve"
        )
        self.assertEqual(row.before_state["status"], TicketStatus.IN_PROGRESS)

    def test_the_priority_audit_row_records_the_committed_value(self):
        """`before` has to come from the locked row, not from the instance.

        The view reads the ticket, then waits for the lock. Anything that
        changed it in between is already committed, and an audit row naming
        the value it replaced is the only record of what actually happened.

        ⚠️ This used to commit the competing change *before* issuing the
        request, and passed with the read moved back above the lock: the view
        re-reads the row on entry, so the stale value it was supposed to catch
        never existed. The change has to land inside the window, which means
        driving it from ``_lock`` itself.
        """
        ticket = self.make_ticket(priority=TicketPriority.LOW)
        self.client.force_login(self.admin)
        real_lock = lifecycle._lock

        def change_then_lock(t):
            Ticket.objects.filter(pk=t.pk).update(priority=TicketPriority.NORMAL)
            return real_lock(t)

        with patch.object(lifecycle, "_lock", side_effect=change_then_lock):
            self.client.patch(
                f"{QUEUE}{ticket.pk}/", {"priority": TicketPriority.HIGH},
                format="json",
            )

        row = AuditLog.objects.get(
            entity_type="ticket", entity_id=ticket.pk, action="priority"
        )
        self.assertEqual(row.before_state["priority"], TicketPriority.NORMAL)
        self.assertEqual(row.after_state["priority"], TicketPriority.HIGH)

    def test_deleting_twice_is_a_404_not_a_second_audit_row(self):
        ticket = self.make_ticket()
        self.client.force_login(self.admin)
        self.client.delete(self.url(ticket))

        second = self.client.delete(self.url(ticket))

        self.assertEqual(second.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            AuditLog.objects.filter(
                entity_type="ticket", entity_id=ticket.pk, action="delete"
            ).count(),
            1,
        )


class SupportEndpointPermissionTests(AdminTicketAPITestCase):
    """Every support endpoint refuses an ordinary logged-in user.

    Written after a coverage pass found that ``permission_classes`` could be
    deleted from eleven of these views with the whole suite still green.
    Deleting the line does not open a hole that shows up as a crash: the
    project-wide default in settings takes over, that default is
    ``IsAuthenticated``, and so any student with an account walks in. On the
    three worst views that means reading internal notes on a stranger's
    ticket, downloading the files attached to them, and posting a message
    signed "Support".

    The assertion is the one that fails on that mutation. A missing
    ``permission_classes`` turns these 403s into 200/400/404, so each row here
    pins one view's gate. Anonymous is checked in the same table because the
    two identities fail through different code and a fix for one has silently
    left the other open before.

    ⚠️ Add a row whenever a URL is added to urls_admin.py. The table cannot be
    generated, because each row states *which* gate the route should have and
    only a person knows that. But "did you remember at all" can be checked
    without a table, and is — see
    ``test_every_admin_route_declares_its_own_permission_classes`` below. An
    earlier version of this docstring claimed no self-updating check was
    possible; a review pass disproved it by adding a route with no
    ``permission_classes`` and watching the whole suite stay green.
    """

    def operations(self):
        """(label, callable) for every route in urls_admin.py.

        Bodies are deliberately valid-ish: a 400 from validation still proves
        the gate let the caller past, which is exactly what must not happen.
        """
        t = self.ticket.pk
        return [
            ("GET queue", lambda: self.client.get(QUEUE)),
            ("GET summary", lambda: self.client.get(f"{QUEUE}summary/")),
            ("GET assignees", lambda: self.client.get(f"{QUEUE}assignees/")),
            ("GET regions", lambda: self.client.get(f"{QUEUE}regions/")),
            ("POST bulk-assign", lambda: self.client.post(
                f"{QUEUE}bulk-assign/",
                {"ticketIds": [t], "assigneeId": self.agent.pk}, format="json")),
            ("GET detail", lambda: self.client.get(f"{QUEUE}{t}/")),
            ("PATCH detail", lambda: self.client.patch(
                f"{QUEUE}{t}/", {"priority": "high"}, format="json")),
            ("GET history", lambda: self.client.get(f"{QUEUE}{t}/history/")),
            ("POST message", lambda: self.client.post(
                f"{QUEUE}{t}/messages/",
                {"messageType": "internal_note", "body": "hi"}, format="json")),
            ("GET attachment", lambda: self.client.get(f"{QUEUE}{t}/attachments/1/")),
            ("GET support-scope", lambda: self.client.get(f"{QUEUE}support-scope/")),
            ("POST support-scope", lambda: self.client.post(
                f"{QUEUE}support-scope/", {"userId": self.outsider.pk}, format="json")),
            ("DELETE support-scope", lambda: self.client.delete(
                f"{QUEUE}support-scope/{self.agent.pk}/")),
            ("DELETE ticket", lambda: self.client.delete(f"{QUEUE}{t}/delete/")),
        ]

    # Routes that are not merely support-only but admin-only (DEC-024 for the
    # delete, the roster for the other three). Downgrading any of these to
    # SUPPORT_PERMISSIONS is a one-word edit that used to pass the suite.
    ADMIN_ONLY = {
        "GET support-scope", "POST support-scope",
        "DELETE support-scope", "DELETE ticket",
    }

    def setUp(self):
        super().setUp()
        self.ticket = self.make_ticket()

    def test_every_admin_route_declares_its_own_permission_classes(self):
        """The table above cannot notice a route nobody added a row for.

        A new endpoint written without ``permission_classes`` inherits the
        project default, ``IsAuthenticated``, and that is the whole hole: any
        signed-in student reaches it. No request-level test fires, because no
        test knows the route exists.

        Reading the urlconf does notice. This asserts each view declares the
        line *itself* — ``__dict__`` rather than ``getattr``, or APIView's
        inherited default would satisfy it — and that what it declares names
        one of this app's own gates rather than only ``IsAuthenticated``.
        """
        from apps.admin.permissions import IsAdminScoped
        from apps.tickets import urls_admin
        from apps.tickets.permissions import IsSupportScoped

        ticket_gates = {IsSupportScoped, IsAdminScoped}
        offenders = []
        for pattern in urls_admin.urlpatterns:
            view = getattr(pattern.callback, "cls", None)
            if view is None:                       # not an APIView route
                continue
            declared = view.__dict__.get("permission_classes")
            if declared is None:
                offenders.append(f"{view.__name__} ({pattern.name}): no permission_classes")
            elif not ticket_gates.intersection(declared):
                offenders.append(
                    f"{view.__name__} ({pattern.name}): "
                    f"declares {[c.__name__ for c in declared]}, none of them a ticket gate"
                )

        self.assertEqual(
            offenders, [],
            "OFFENDER: a support route is reachable by any signed-in user — " + "; ".join(offenders),
        )

    def test_an_ordinary_logged_in_user_is_refused_everywhere(self):
        self.client.force_login(self.outsider)
        for label, call in self.operations():
            with self.subTest(operation=label):
                self.assertEqual(
                    call().status_code, status.HTTP_403_FORBIDDEN,
                    f"{label} let a user with no support or admin row through",
                )

    def test_an_anonymous_caller_is_refused_everywhere(self):
        self.client.logout()
        for label, call in self.operations():
            with self.subTest(operation=label):
                self.assertEqual(
                    call().status_code, status.HTTP_403_FORBIDDEN,
                    f"{label} answered an anonymous caller",
                )

    def test_the_admin_only_routes_refuse_a_support_agent(self):
        """The line between "can work the queue" and "can change who can".

        self.agent has a SupportScope row and no AdminScope row, which is the
        whole point of the role existing (p47). These four are the operations
        that role must not reach, and each is one word away from being opened
        to it.
        """
        self.client.force_login(self.agent)
        for label, call in self.operations():
            if label not in self.ADMIN_ONLY:
                continue
            with self.subTest(operation=label):
                self.assertEqual(
                    call().status_code, status.HTTP_403_FORBIDDEN,
                    f"{label} was reachable by a support agent who is not an admin",
                )

    def test_a_support_agent_reaches_every_route_that_is_not_admin_only(self):
        """The other half: the gates must not be so tight the role is useless.

        Without this, tightening every view to IsAdminScoped would also pass
        the three tests above.
        """
        self.client.force_login(self.agent)
        for label, call in self.operations():
            if label in self.ADMIN_ONLY:
                continue
            with self.subTest(operation=label):
                self.assertNotEqual(
                    call().status_code, status.HTTP_403_FORBIDDEN,
                    f"{label} refused a support agent who should be able to use it",
                )


class MeEndpointTests(AdminTicketAPITestCase):
    def flags_for(self, user):
        self.client.force_login(user)
        payload = self.client.get("/api/v1/users/me/").json()
        return payload["isAdmin"], payload["isSupport"]

    def test_an_agent_is_support_but_not_admin(self):
        self.assertEqual(self.flags_for(self.agent), (False, True))

    def test_an_admin_is_both(self):
        # One flag could not tell these two rows apart, which is why the
        # endpoint returns two.
        self.assertEqual(self.flags_for(self.admin), (True, True))

    def test_an_ordinary_user_is_neither(self):
        self.assertEqual(self.flags_for(self.outsider), (False, False))

    def test_patching_my_profile_returns_the_flags_too(self):
        # GET and PATCH on the same endpoint have to answer with the same
        # shape. A client that changes its timezone and stores the reply
        # would otherwise lose both flags and stop showing the queue.
        self.client.force_login(self.agent)
        response = self.client.patch(
            "/api/v1/users/me/", {"timezone": "Australia/Sydney"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("isAdmin", response.json())
        self.assertTrue(response.json()["isSupport"])

    def test_the_user_list_response_did_not_grow_the_two_flags(self):
        self.client.force_login(self.admin)
        rows = self.client.get("/api/v1/admin/user/").json()["data"]["items"]
        self.assertTrue(rows)
        self.assertNotIn("isSupport", rows[0])


class QueueSummaryCountTests(AdminTicketAPITestCase):
    """Each counter card counts its own thing.

    Four numbers on the queue page, and swapping which status two of them read
    left the suite green — the cards would have been confidently wrong, which
    is worse than blank, because an agent works from them.
    """

    def counts(self):
        return self.client.get(f"{QUEUE}summary/").json()["data"]

    def test_each_card_counts_only_its_own_status(self):
        """Every observable number is pairwise distinct, on purpose.

        ⚠️ This test has now been rewritten twice for the same class of hole,
        so the rule it follows is spelled out. Version one built one ticket
        per status: 1/1/1, so a card reading the wrong status still returned
        1. Version two used 3/2/1 — which fixed open and pendingUser and left
        unassigned equal to open at 3, so wiring unassigned to count
        ``status=OPEN`` still passed. The invariant a counting test needs is
        that the expected value differs from what EVERY plausible miswiring
        would produce, which here means: no two of {open, pendingUser,
        in-progress, unassigned, unassigned-without-its-exclusion} may agree.

        Data: 4 open unowned · 2 pending owned + 1 pending unowned ·
        1 in-progress owned · 1 resolved unowned.
        → open 4, pendingUser 3, unassigned 5 (and 6 if the resolved
        exclusion is dropped). All pairwise distinct.
        """
        for i in range(4):
            self.make_ticket(subject=f"Nobody has this {i}")          # open, unowned
        for i in range(2):
            waiting = self.make_ticket(subject=f"Waiting on them {i}")
            lifecycle.assign(ticket=waiting, actor=self.admin, assignee=self.agent)
            lifecycle.mark_pending(ticket=waiting, actor=self.agent)
        # Pending with no owner — reached in the product via the status
        # dropdown (T8), which never touches the assignee.
        drifting = self.make_ticket(subject="Waiting on them, ownerless")
        lifecycle.set_status(
            ticket=drifting, new_status=TicketStatus.PENDING_USER, actor=self.agent
        )
        working = self.make_ticket(subject="Being worked on")
        lifecycle.assign(ticket=working, actor=self.admin, assignee=self.agent)
        finished = self.make_ticket(subject="Done, never owned")
        lifecycle.resolve(ticket=finished, actor=self.agent)

        counts = self.counts()

        self.assertEqual(counts["open"], 4, "open counted something that is not open")
        self.assertEqual(counts["pendingUser"], 3, "pendingUser counted the wrong status")
        self.assertEqual(
            counts["unassigned"], 5,
            "unassigned must count unowned-and-unresolved, nothing else",
        )

    def test_a_resolved_ticket_leaves_the_unassigned_count(self):
        """Resolved-and-unowned is finished work, not a backlog item.

        The card is what an agent uses to decide what to pick up next, so a
        resolved ticket sitting in it sends them looking for work that is
        already done.
        """
        ticket = self.make_ticket()
        self.assertEqual(self.counts()["unassigned"], 1)

        lifecycle.resolve(ticket=ticket, actor=self.agent)

        self.assertEqual(self.counts()["unassigned"], 0)

    def test_a_deleted_ticket_leaves_every_count(self):
        self.make_ticket()
        before = self.counts()
        ticket = self.make_ticket(subject="Spam")
        Ticket.objects.filter(pk=ticket.pk).update(deleted_at=timezone.now())

        self.assertEqual(self.counts(), before)


class RegionDropdownTests(AdminTicketAPITestCase):
    """What the region filter offers, which is derived and not configured."""

    def options(self):
        return self.client.get(f"{QUEUE}regions/").json()["data"]

    def test_a_region_in_use_by_several_tickets_is_offered_once(self):
        # Without .distinct() the dropdown repeats a region once per ticket.
        for _ in range(3):
            ticket = self.make_ticket()
            Ticket.objects.filter(pk=ticket.pk).update(region="Australia")

        values = [option["value"] for option in self.options()]

        self.assertEqual(values.count("Australia"), 1, f"repeated entries: {values}")

    def test_the_blank_region_is_never_offered_as_its_own_option(self):
        # Tickets with no known country carry "". Offering that as a value
        # gives the dropdown an entry that silently clears the filter, while
        # the Unknown bucket below is the sentinel that actually selects them.
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(region="")

        values = [option["value"] for option in self.options()]

        self.assertNotIn("", values)
        self.assertEqual(values[-1], "__unknown__", "the Unknown bucket must come last")


class QueueSearchFieldTests(AdminTicketAPITestCase):
    """Search reaches all three requester fields, not just the first name.

    ⚠️ Each probe term must be reachable through exactly ONE branch of the
    search OR. The first version searched "Mia" for the first-name test, and
    the requester's email is mia@example.com — an icontains hit through the
    email branch, so the first-name branch could be deleted with the test
    green. The fixtures' emails are derived from their first names, which
    makes them exactly the wrong users to probe the name branches with.
    """

    def found(self, term):
        return {
            row["id"]
            for row in self.client.get(QUEUE, {"search": term}).json()["data"]["items"]
        }

    def one_branch_requester(self):
        """A requester none of whose search fields shadow another."""
        return User.objects.create_user(
            # "Priya" is not a substring of the email; "Nair" is not either;
            # the mailbox name overlaps neither name.
            email="pk2041@example.com", password="pass1234",
            first_name="Priya", last_name="Nair",
        )

    def test_search_matches_the_requesters_last_name(self):
        ticket = self.make_ticket(owner=self.one_branch_requester())
        self.assertEqual(self.found("Nair"), {ticket.pk})

    def test_search_matches_the_requesters_first_name(self):
        ticket = self.make_ticket(owner=self.one_branch_requester())
        self.assertEqual(self.found("Priya"), {ticket.pk})

    def test_search_matches_the_requesters_email(self):
        ticket = self.make_ticket(owner=self.one_branch_requester())
        self.assertEqual(self.found("pk2041"), {ticket.pk})

    def test_search_matches_the_subject_and_the_number(self):
        ticket = self.make_ticket(subject="Printer on fire")
        self.assertEqual(self.found("Printer"), {ticket.pk})
        self.assertEqual(self.found(ticket.ticket_number), {ticket.pk})


class AdminAttachmentAccessTests(AdminTicketAPITestCase):
    """The support-side download's conditions, one mutation each.

    The requester-side twin of this class already existed; this side had only
    positive coverage, so ``message__ticket_id`` or either ``deleted_at``
    condition could be deleted with the whole suite green. The view's
    docstring says the queryset IS the access control, which is exactly why
    each of its conditions needs a test that fails without it.
    """

    def setUp(self):
        super().setUp()
        self.other_ticket = self.make_ticket(subject="Unrelated")
        self.ticket = self.make_ticket(subject="With a file")
        with self.captureOnCommitCallbacks(execute=True):
            with stored_attachments([pdf()]) as rows:
                message = lifecycle.add_support_reply(
                    ticket=self.ticket, actor=self.agent, body="See attached.",
                    attachments=rows,
                )
        self.attachment_id = message.attachments.first().pk

    def url(self, ticket):
        return f"{QUEUE}{ticket.pk}/attachments/{self.attachment_id}/"

    def test_an_agent_can_download_it_through_its_own_ticket(self):
        response = self.client.get(self.url(self.ticket))
        self.assertIn(
            response.status_code, (status.HTTP_200_OK, status.HTTP_302_FOUND)
        )

    def test_it_cannot_be_fetched_through_another_tickets_url(self):
        # Attachment ids are sequential and guessable. Without the ticket_id
        # condition, any ticket id in the path opens any attachment id.
        response = self.client.get(self.url(self.other_ticket))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_an_attachment_on_a_deleted_ticket_is_gone(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(deleted_at=timezone.now())
        response = self.client.get(self.url(self.ticket))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_an_attachment_on_a_deleted_message_is_gone(self):
        self.ticket.messages.update(deleted_at=timezone.now())
        response = self.client.get(self.url(self.ticket))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_an_internal_note_attachment_is_downloadable_here(self):
        """The deliberate asymmetry with the requester side, pinned.

        Tightening this view by pasting in the requester's internal-note
        exclusion would break the one thing this view exists for: agents
        working from files colleagues attached to notes.
        """
        with self.captureOnCommitCallbacks(execute=True):
            with stored_attachments([pdf("internal.pdf")]) as rows:
                note = lifecycle.add_internal_note(
                    ticket=self.ticket, actor=self.agent, body="For us.",
                    attachments=rows,
                )
        response = self.client.get(
            f"{QUEUE}{self.ticket.pk}/attachments/{note.attachments.first().pk}/"
        )
        self.assertIn(
            response.status_code, (status.HTTP_200_OK, status.HTTP_302_FOUND)
        )


class QueueEnvelopeTests(AdminTicketAPITestCase):
    """The pagination envelope: total and hasMore, both previously unpinned.

    The queue's page bar is driven entirely by these two numbers. Both could
    be miswired with the suite green — total to the page's row count, hasMore
    to a constant — and the bar would then either hide pages or offer pages
    that do not exist.
    """

    def test_total_counts_the_whole_queue_not_the_page(self):
        for i in range(3):
            self.make_ticket(subject=f"Ticket {i}")

        data = self.client.get(QUEUE, {"page": 1, "limit": 2}).json()["data"]

        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["total"], 3, "total reported the page, not the queue")

    def test_has_more_flips_exactly_at_the_last_page(self):
        for i in range(3):
            self.make_ticket(subject=f"Ticket {i}")

        first = self.client.get(QUEUE, {"page": 1, "limit": 2}).json()["data"]
        last = self.client.get(QUEUE, {"page": 2, "limit": 2}).json()["data"]

        self.assertTrue(first["hasMore"], "a second page exists and was not offered")
        self.assertFalse(last["hasMore"], "a page was offered past the end")

    def test_an_id_beyond_bigint_is_a_400_like_any_other_nonsense(self):
        # int() accepts any number of digits, database id columns do not.
        # Unguarded, this crashed SQLite with an OverflowError (a 500 for a
        # number in the query string) while Postgres returned an empty 200 —
        # the same request, two different answers, neither of them a 400.
        response = self.client.get(QUEUE, {"assignee": str(2 ** 64)})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DeleteAuditRecordTests(AdminTicketAPITestCase):
    """What the delete audit row must carry, field by field.

    The row is the ONLY record that survives a deletion — the ticket leaves
    every queryset, so there is no joining back to it later. Each field here
    answers a question someone will actually ask ("whose ticket was that?",
    "was it still open?"), and each could previously be dropped from the
    snapshot with the whole suite green.
    """

    def delete_and_fetch_row(self, ticket):
        self.client.force_login(self.admin)
        response = self.client.delete(f"{QUEUE}{ticket.pk}/delete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return AuditLog.objects.get(
            entity_type="ticket", entity_id=ticket.pk, action="delete"
        )

    def test_the_row_names_the_status_the_ticket_died_in(self):
        ticket = self.make_ticket()
        lifecycle.assign(ticket=ticket, actor=self.admin, assignee=self.agent)

        row = self.delete_and_fetch_row(ticket)

        self.assertEqual(row.before_state["status"], TicketStatus.IN_PROGRESS)

    def test_the_row_names_whose_ticket_it_was(self):
        ticket = self.make_ticket()

        row = self.delete_and_fetch_row(ticket)

        self.assertEqual(row.before_state["created_by_id"], self.requester.pk)
        self.assertEqual(row.before_state["ticket_number"], ticket.ticket_number)
        self.assertEqual(row.before_state["subject"], ticket.subject)


class RosterAuditAtomicityTests(AdminTicketAPITestCase):
    """A grant and its audit row land together or not at all.

    Split across two transactions, a crash between them leaves someone with
    support access and no record of who gave it — on a platform whose users
    are minors, an unexplained grant is the worst kind.
    """

    def test_a_grant_whose_audit_write_fails_does_not_stick(self):
        self.client.force_login(self.admin)

        with patch(
            "apps.tickets.views_admin.log_audit_event",
            side_effect=RuntimeError("audit store down"),
        ):
            response = self.client.post(
                f"{QUEUE}support-scope/", {"userId": self.outsider.pk}
            )

        self.assertEqual(response.status_code, 500)
        self.assertFalse(
            SupportScope.objects.filter(user=self.outsider).exists(),
            "support access was granted with no audit row to say who did it",
        )


class ConfiguredDefaultsTests(AdminTicketAPITestCase):
    """Numbers that live in settings and drive user-visible behaviour.

    Only the HIGH SLA was pinned. NORMAL and LOW could be multiplied by a
    hundred with the suite green, and the Overdue card — the number an agent
    triages by — would quietly stop flagging almost everything.
    """

    def test_the_three_sla_defaults_are_what_the_oral_exam_says_they_are(self):
        from apps.tickets.services.queue import _sla_hours
        from apps.tickets.models import TicketPriority

        self.assertEqual(_sla_hours(), {
            TicketPriority.HIGH: 4,
            TicketPriority.NORMAL: 24,
            TicketPriority.LOW: 72,
        })


class MeEndpointContractTests(AdminTicketAPITestCase):
    """The /users/me/ payload as the two frontends' shared login contract.

    Both apps decide what to render from this one response. id keys the
    client-side caches, last_name renders anywhere a full name does, and
    account_status gates "should this session even be here" — and each could
    be deleted from the serializer with every test green.
    """

    REQUIRED_FIELDS = ("id", "email", "first_name", "last_name", "account_status")

    def test_the_get_payload_carries_every_contract_field(self):
        self.client.force_login(self.agent)
        payload = self.client.get("/api/v1/users/me/").json()
        for field in self.REQUIRED_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, payload)
        self.assertEqual(payload["id"], self.agent.pk)
        self.assertEqual(payload["last_name"], "Reid")

    def test_the_patch_payload_matches_the_get_payload(self):
        self.client.force_login(self.agent)
        get_keys = set(self.client.get("/api/v1/users/me/").json().keys())
        patch_keys = set(
            self.client.patch(
                "/api/v1/users/me/", {"timezone": "Australia/Sydney"}, format="json"
            ).json().keys()
        )
        self.assertEqual(get_keys, patch_keys)
class ReplyAndMoveToPendingEndpointTests(AdminTicketAPITestCase):
    """The one-request version of "answer them, then wait for their answer"."""

    def test_the_flag_moves_the_ticket_in_the_same_request(self):
        ticket = self.make_ticket()
        response = self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {
                "messageType": "support_reply",
                "body": "Could you send a screenshot?",
                "moveToPending": True,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        # The response body is the detail payload, so the panel repaints with
        # the new status instead of showing a stale one until the next fetch.
        self.assertEqual(response.json()["data"]["status"], TicketStatus.PENDING_USER)

    def test_omitting_the_flag_leaves_the_status_alone(self):
        ticket = self.make_ticket()
        before = ticket.status
        response = self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {"messageType": "support_reply", "body": "Looking into it now."},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, before)

    def test_an_internal_note_may_not_move_the_ticket(self):
        """Rejected rather than ignored: silently dropping the flag would move
        the ball to a requester who cannot see anything asking them for it.
        """
        ticket = self.make_ticket()
        before = ticket.status
        response = self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {
                "messageType": "internal_note",
                "body": "Escalating internally.",
                "moveToPending": True,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, before)
        self.assertEqual(ticket.messages.filter(body="Escalating internally.").count(), 0)

    def test_the_status_change_is_filed_under_the_agent_who_replied(self):
        ticket = self.make_ticket()
        self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {
                "messageType": "support_reply",
                "body": "Could you send a screenshot?",
                "moveToPending": True,
            },
        )
        row = (
            AuditLog.objects.filter(entity_type="ticket", action="status")
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(row)
        self.assertEqual(row.actor_user_id, self.agent.pk)
        self.assertEqual(row.after_state["status"], TicketStatus.PENDING_USER)


class UnassignedFilterTests(AdminTicketAPITestCase):
    """The Unassigned card had a number nobody could click through to."""

    def setUp(self):
        super().setUp()
        self.owned = self.make_ticket(subject="Someone is on this")
        lifecycle.claim(ticket=self.owned, actor=self.agent)
        self.free = self.make_ticket(subject="Nobody has this")
        # Unowned *and* resolved. Without one of these in the fixture the
        # parity assertion below passes whatever the filter does, because the
        # card's .exclude(status=RESOLVED) has nothing to exclude. This is the
        # row that tells the two definitions apart.
        self.settled = self.make_ticket(subject="Nobody has this, and it is done")
        lifecycle.resolve(ticket=self.settled, actor=self.agent)

    def ids_for(self, **params):
        return {row["id"] for row in self.client.get(QUEUE, params).json()["data"]["items"]}

    def test_the_unassigned_bucket_is_selectable(self):
        self.assertEqual(self.ids_for(assignee="__unassigned__"), {self.free.pk})

    def test_the_sentinel_is_not_read_as_an_id(self):
        """It is intercepted before the int() coercion.

        That coercion is why the sentinel had to live in this function rather
        than in a serializer: reaching it would answer 400 for a value the
        dropdown itself offers.
        """
        response = self.client.get(QUEUE, {"assignee": "__unassigned__"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_genuine_non_number_is_still_a_400(self):
        response = self.client.get(QUEUE, {"assignee": "nonsense"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filtering_by_a_real_agent_still_works(self):
        self.assertEqual(self.ids_for(assignee=str(self.agent.pk)), {self.owned.pk})

    def test_a_resolved_ticket_with_no_owner_is_not_in_the_bucket(self):
        """It has no owner, but it is not waiting for one.

        The card reads "unowned and not resolved". A filter that only asked
        for "unowned" would list this row under a number that never counted
        it, which is the kind of mismatch an agent notices immediately: a
        card saying 1 opening a list of 2.
        """
        self.assertNotIn(self.settled.pk, self.ids_for(assignee="__unassigned__"))

    def test_the_count_and_the_filter_agree(self):
        """The card and the list it filters to are computed separately, so
        this is the assertion that keeps them honest.

        setUp seeds a resolved unowned ticket precisely so this comparison
        has something to catch.
        """
        summary = self.client.get(f"{QUEUE}summary/").json()["data"]
        self.assertEqual(
            summary["unassigned"], len(self.ids_for(assignee="__unassigned__"))
        )


class HandBackToThePoolTests(AdminTicketAPITestCase):
    """Giving a ticket back. The owner control used to be one-way."""

    def test_a_null_assignee_clears_the_owner(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/", {"assignee": None}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.assignee_id)

    def test_handing_back_tells_the_requester_nothing(self):
        """Who owns it is not the requester's business (DEC-017), and their
        clock must not move for something invisible to them.
        """
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        messages_before = ticket.messages.count()
        updated_before = ticket.updated_at

        self.client.patch(f"{QUEUE}{ticket.pk}/", {"assignee": None}, format="json")

        ticket.refresh_from_db()
        self.assertEqual(ticket.messages.count(), messages_before)
        self.assertEqual(ticket.updated_at, updated_before)

    def test_handing_back_is_filed_in_the_audit_log(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        self.client.patch(f"{QUEUE}{ticket.pk}/", {"assignee": None}, format="json")

        row = (
            AuditLog.objects.filter(entity_type="ticket", action="assign")
            .order_by("-created_at")
            .first()
        )
        self.assertEqual(row.before_state["assignee_id"], self.agent.pk)
        self.assertIsNone(row.after_state["assignee_id"])

    def test_releasing_an_open_ticket_is_not_mistaken_for_picking_it_up(self):
        """The trap this whole item walks into.

        "Picked up from the pool" was decided by status alone. A ticket that
        is open and already ownerless would therefore read as a pick-up when
        somebody released it: the requester gets told their ticket is now
        being handled, and the status moves to in progress, on a ticket that
        nobody is working.
        """
        ticket = self.make_ticket()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        messages_before = ticket.messages.count()

        self.client.patch(f"{QUEUE}{ticket.pk}/", {"assignee": None}, format="json")

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertEqual(ticket.messages.count(), messages_before)

    def test_a_handed_back_ticket_shows_up_in_the_unassigned_bucket(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        self.client.patch(f"{QUEUE}{ticket.pk}/", {"assignee": None}, format="json")

        ids = {
            row["id"]
            for row in self.client.get(
                QUEUE, {"assignee": "__unassigned__"}
            ).json()["data"]["items"]
        }
        self.assertIn(ticket.pk, ids)


class RosterScreenTests(AdminTicketAPITestCase):
    """What the roster screen needs, and the guards nothing was pinning.

    The grant endpoint had a 403 test; the list and the revoke did not, even
    though all three are the admin-only half of this module. A support agent
    reaching the roster could hand themselves an admin-only capability.
    """

    def test_a_support_agent_cannot_read_the_roster(self):
        # self.agent is support but not an admin — the case the role exists for.
        response = self.client.get(f"{QUEUE}support-scope/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_a_support_agent_cannot_revoke(self):
        SupportScope.objects.create(user=self.outsider)
        response = self.client.delete(f"{QUEUE}support-scope/{self.outsider.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(SupportScope.objects.filter(user=self.outsider).exists())

    def test_an_admin_sees_the_roster(self):
        self.client.force_login(self.admin)
        rows = self.client.get(f"{QUEUE}support-scope/").json()["data"]
        self.assertIn(self.agent.pk, [row["id"] for row in rows])

    def test_each_row_says_how_much_work_revoking_would_strand(self):
        """The number the confirmation dialog needs.

        Revoking somebody who still owns live tickets does not move those
        tickets, so without this the admin cannot see what they are about to
        orphan.
        """
        mine = self.make_ticket(subject="Still open")
        lifecycle.claim(ticket=mine, actor=self.agent)
        done = self.make_ticket(subject="Already finished")
        lifecycle.claim(ticket=done, actor=self.agent)
        lifecycle.resolve(ticket=done, actor=self.agent)

        self.client.force_login(self.admin)
        rows = self.client.get(f"{QUEUE}support-scope/").json()["data"]
        row = next(r for r in rows if r["id"] == self.agent.pk)

        # Resolved is excluded: nobody has to pick that one up again.
        self.assertEqual(row["openTickets"], 1)

    def test_a_deleted_ticket_does_not_count_against_them(self):
        ticket = self.make_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.soft_delete(ticket=ticket, actor=self.admin)

        self.client.force_login(self.admin)
        rows = self.client.get(f"{QUEUE}support-scope/").json()["data"]
        row = next(r for r in rows if r["id"] == self.agent.pk)
        self.assertEqual(row["openTickets"], 0)

    def test_the_roster_comes_back_in_a_stable_order(self):
        """Weak on purpose, and worth saying why.

        The view orders by first_name, last_name, email. first_name alone is
        not a total order — it is blank for anyone invited but never
        onboarded — so without the tiebreakers those rows come back in
        whatever order the database chooses.

        This test cannot prove the tiebreakers are there. Dropping them and
        re-running it stays green on PostgreSQL: the Count annotation puts a
        GROUP BY in the query, and the grouping happens to emit these rows in
        an order that satisfies any assertion about them. (On SQLite the same
        mutation does fail, which is the trap — a mutation that dies on the
        test database and survives on the real one reads as proof and is not.)

        So this asserts only what is genuinely observable: two identical
        requests agree. The tiebreakers themselves are held by review, not by
        this test.
        """
        for address in ("zzz@example.com", "aaa@example.com"):
            SupportScope.objects.create(
                user=User.objects.create_user(
                    email=address, password="pass1234", first_name="", last_name="",
                )
            )
        self.client.force_login(self.admin)

        first = [r["id"] for r in self.client.get(f"{QUEUE}support-scope/").json()["data"]]
        second = [r["id"] for r in self.client.get(f"{QUEUE}support-scope/").json()["data"]]
        self.assertEqual(first, second)


class TicketAuditViewTests(AdminTicketAPITestCase):
    """The record the delete dialog promises exists.

    The per-ticket history endpoint looks the ticket up through live_tickets()
    first, so a deleted ticket's own history 404s — the one action whose
    record matters most was the one nothing could show.
    """

    def audit(self, **params):
        return self.client.get(f"{QUEUE}audit/", params).json()["data"]

    def test_a_deleted_tickets_own_history_is_unreachable(self):
        """Pins the reason this endpoint exists. If this ever starts passing,
        the per-ticket history got fixed and this view may be redundant.
        """
        ticket = self.make_ticket()
        lifecycle.soft_delete(ticket=ticket, actor=self.admin)
        response = self.client.get(f"{QUEUE}{ticket.pk}/history/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_the_deletion_is_still_readable_here(self):
        ticket = self.make_ticket(subject="Spam about crypto")
        number = ticket.ticket_number
        lifecycle.soft_delete(ticket=ticket, actor=self.admin)

        rows = self.audit(action="delete")["items"]
        row = next(r for r in rows if r["ticketId"] == ticket.pk)
        self.assertEqual(row["actor"]["id"], self.admin.pk)
        # Identified without joining back to a row no queryset returns.
        self.assertEqual(row["beforeState"]["ticket_number"], number)
        self.assertEqual(row["beforeState"]["subject"], "Spam about crypto")

    def test_a_support_agent_can_read_it(self):
        """Matches the per-ticket history, not the admin-only delete action.

        An agent who watched a ticket vanish should be able to see that it was
        deleted rather than wonder whether they imagined it.
        """
        ticket = self.make_ticket()
        lifecycle.soft_delete(ticket=ticket, actor=self.admin)
        self.client.force_login(self.agent)
        response = self.client.get(f"{QUEUE}audit/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_somebody_with_neither_role_is_refused(self):
        self.client.force_login(self.outsider)
        response = self.client.get(f"{QUEUE}audit/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_filtering_by_action(self):
        kept = self.make_ticket()
        lifecycle.claim(ticket=kept, actor=self.agent)
        binned = self.make_ticket()
        lifecycle.soft_delete(ticket=binned, actor=self.admin)

        actions = {r["action"] for r in self.audit(action="delete")["items"]}
        self.assertEqual(actions, {"delete"})

    def test_an_unknown_action_returns_nothing_rather_than_erroring(self):
        """Free text on this model: log_audit_event does not validate against
        ActionChoices, and the ticket module writes seven values of which only
        three are in that enum. So an unfamiliar value is a filter that matches
        nothing, not a bad request.
        """
        response = self.client.get(f"{QUEUE}audit/", {"action": "nonsense"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["items"], [])

    def test_filtering_by_actor(self):
        mine = self.make_ticket()
        lifecycle.claim(ticket=mine, actor=self.agent)
        theirs = self.make_ticket()
        lifecycle.soft_delete(ticket=theirs, actor=self.admin)

        rows = self.audit(actor=str(self.admin.pk))["items"]
        self.assertTrue(rows)
        self.assertTrue(all(r["actor"]["id"] == self.admin.pk for r in rows))

    def test_a_non_numeric_actor_is_a_400(self):
        response = self.client.get(f"{QUEUE}audit/", {"actor": "nonsense"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_pages_with_the_same_key_as_the_queue(self):
        """hasMore, not has_more. The platform is split between the two
        spellings and the ticket endpoints all use this one.
        """
        for _ in range(3):
            lifecycle.claim(ticket=self.make_ticket(), actor=self.agent)

        first = self.audit(limit=2, page=1)
        self.assertIn("hasMore", first)
        self.assertEqual(len(first["items"]), 2)
        self.assertTrue(first["hasMore"])

        last = self.audit(limit=2, page=99)
        self.assertFalse(last["hasMore"])

    def test_newest_first(self):
        first_ticket = self.make_ticket()
        lifecycle.claim(ticket=first_ticket, actor=self.agent)
        second_ticket = self.make_ticket()
        lifecycle.soft_delete(ticket=second_ticket, actor=self.admin)

        items = self.audit()["items"]
        self.assertEqual(items[0]["ticketId"], second_ticket.pk)

    def test_it_shows_only_ticket_rows(self):
        """support_scope grants land in the same table under a different
        entity_type. Leaking them in here would put a person's id in a column
        the screen labels as a ticket.
        """
        self.client.force_login(self.admin)
        self.client.post(f"{QUEUE}support-scope/", {"userId": self.outsider.pk})
        ticket = self.make_ticket()
        lifecycle.soft_delete(ticket=ticket, actor=self.admin)

        ids = {r["ticketId"] for r in self.audit()["items"]}
        self.assertIn(ticket.pk, ids)
        self.assertNotIn(self.outsider.pk, ids - {ticket.pk})


class TicketAnalyticsEndpointTests(AdminTicketAPITestCase):
    """The dashboard endpoint. The measures themselves are asserted against a
    fixed data set in test_analytics.py; this is the door, not the room.
    """

    URL = f"{QUEUE}analytics/"

    def test_a_support_agent_can_read_it(self):
        """They are the people the numbers are about."""
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_somebody_with_neither_role_is_refused(self):
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(self.URL).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_it_answers_with_all_four_measure_groups(self):
        self.make_ticket()
        data = self.client.get(self.URL).json()["data"]
        for group in ("demand", "flow", "service", "quality"):
            self.assertIn(group, data)

    def test_an_unknown_dimension_is_rejected_rather_than_ignored(self):
        """A typo that silently returns the unsegmented set looks like a
        segment with one bucket, which is a wrong answer rather than an error.
        """
        response = self.client.get(self.URL, {"dimension": "programStage"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_every_advertised_dimension_is_accepted(self):
        self.make_ticket()
        for dimension in self.client.get(self.URL).json()["data"]["dimensions"]:
            with self.subTest(dimension=dimension):
                response = self.client.get(self.URL, {"dimension": dimension})
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_plain_date_is_accepted_and_read_as_utc_midnight(self):
        response = self.client.get(self.URL, {"from": "2026-03-01"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["data"]["window"]["from"], "2026-03-01T00:00:00+00:00"
        )

    def test_a_nonsense_date_is_a_400(self):
        response = self.client.get(self.URL, {"from": "last tuesday"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_backwards_window_is_a_400(self):
        response = self.client.get(
            self.URL, {"from": "2026-03-01", "to": "2026-02-01"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class SnapshotPagingTests(AdminTicketAPITestCase):
    """Paging the queue must not lose a ticket, and two designs before this did.

    The defect, measured on a real queue: an agent pages through, somebody
    adds an internal note to a ticket further down, and that ticket is served
    on no page at all while the footer still reads "20 of 20". Two hundred
    tickets, ten to a page, three notes added, three tickets never shown.

    Both earlier attempts are described in services/paging.py. The short
    version is that the queue is ordered by a column that moves while people
    read it, and no ordering makes OFFSET safe against that: a row that
    changes position either crosses the reader itself or shifts the rows
    behind it across the reader, and a set that can shrink does the same thing
    one row at a time.

    So the walk is anchored to the last row it served. The snapshot fixes the
    set and the order among it; the cursor fixes the reader's place in it. The
    two travel together — a request with neither is a fresh look, which is
    what choosing a page number out of the footer is.
    """

    def page(self, **params):
        response = self.client.get(QUEUE, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return response.json()["data"]

    def walk(self, limit=4, on_first_page=None):
        """Page through the whole queue the way Next does, and report what it served.

        ``on_first_page`` runs once, after page one and before page two, which
        is where the reader is when somebody else works a ticket.
        """
        first = self.page(limit=limit)
        seen = [row["id"] for row in first["items"]]
        if on_first_page is not None:
            on_first_page()
        data = first
        while data["hasMore"]:
            data = self.page(limit=limit, asOf=first["asOf"], after=data["after"])
            seen.extend(row["id"] for row in data["items"])
        return seen

    def bump(self, ticket):
        """An internal note: moves the support clock, requester sees nothing."""
        lifecycle.add_internal_note(
            ticket=ticket, actor=self.agent, body="Bumping this one.",
        )

    # ----------------------------------------------------------------- the bug

    def test_a_ticket_nobody_touched_is_never_skipped(self):
        """The regression test for the measured defect. Read this one first.

        The ticket that used to vanish is not the one that changed. It is
        whichever one happened to sit where the reader's offset landed after
        the order moved underneath them.
        """
        made = [self.make_ticket(subject=f"Ticket {i}") for i in range(12)]
        by_id = {t.pk: t for t in made}
        first = self.page(limit=4)
        worked = first["items"][0]["id"]

        seen = self.walk(limit=4, on_first_page=lambda: self.bump(by_id[worked]))

        untouched = set(by_id) - {worked}
        self.assertEqual(
            untouched - set(seen), set(),
            "a ticket nobody touched appeared on no page at all",
        )

    def test_working_a_ticket_the_reader_has_not_reached_loses_nothing_else(self):
        """The shape that cost three tickets on a queue of two hundred.

        Under the capped-sort-key design this was the fatal one: the worked
        ticket was pinned to the snapshot, which is the top of the column, so
        it jumped to position zero — behind a reader already past page one —
        and every page after that was one row short of what it should have
        been.
        """
        made = [self.make_ticket(subject=f"Ticket {i}") for i in range(12)]
        by_id = {t.pk: t for t in made}
        first = self.page(limit=4)
        ahead = [t for t in made if t.pk not in {r["id"] for r in first["items"]}]
        worked = ahead[-1]  # as far in front of the reader as the queue goes

        seen = self.walk(limit=4, on_first_page=lambda: self.bump(worked))

        self.assertEqual(
            set(by_id) - {worked.pk} - set(seen), set(),
            "working one ticket took another one out of the walk with it",
        )

    def test_the_walk_never_serves_the_same_ticket_twice(self):
        """A cursor cannot repeat a row either, and repeats are not free.

        The design this replaces offered duplicates as the acceptable failure —
        visible and harmless. They are neither on a queue an agent is working
        through: the same enquiry answered twice is two people's time.
        """
        made = [self.make_ticket(subject=f"Ticket {i}") for i in range(12)]
        by_id = {t.pk: t for t in made}
        first = self.page(limit=4)
        already_read = first["items"][1]["id"]

        seen = self.walk(limit=4, on_first_page=lambda: self.bump(by_id[already_read]))

        self.assertEqual(len(seen), len(set(seen)))

    def test_a_worked_ticket_leaves_the_walk_and_comes_back_on_a_fresh_one(self):
        """What the reader loses, and why it is the one loss worth having.

        The ticket that disappears is the one somebody just worked, so its
        absence has an owner and an explanation. Every other design so far hid
        a ticket nobody had touched.
        """
        made = [self.make_ticket(subject=f"Ticket {i}") for i in range(5)]
        first = self.page(limit=2)

        self.bump(made[0])

        rest = self.page(limit=2, asOf=first["asOf"], after=first["after"])
        walked = [r["id"] for r in first["items"]] + [r["id"] for r in rest["items"]]
        while rest["hasMore"]:
            rest = self.page(limit=2, asOf=first["asOf"], after=rest["after"])
            walked.extend(r["id"] for r in rest["items"])

        self.assertNotIn(made[0].pk, walked[len(first["items"]):])
        self.assertIn(made[0].pk, [r["id"] for r in self.page(limit=10)["items"]])

    # ------------------------------------------------ membership at the instant

    def test_a_ticket_raised_mid_walk_does_not_join_the_walk(self):
        """Otherwise it arrives at the top, in front of a reader who is past it."""
        made = [self.make_ticket(subject=f"Ticket {i}") for i in range(4)]
        first = self.page(limit=2)

        latecomer = self.make_ticket(subject="Raised while reading")

        rest = self.page(limit=2, asOf=first["asOf"], after=first["after"])
        self.assertNotIn(latecomer.pk, [r["id"] for r in rest["items"]])
        self.assertEqual(rest["total"], first["total"])

    def test_a_ticket_deleted_before_the_walk_is_not_in_it(self):
        gone = self.make_ticket(subject="Already gone")
        lifecycle.soft_delete(ticket=gone, actor=self.agent)
        self.make_ticket(subject="Still here")

        self.assertNotIn(gone.pk, [r["id"] for r in self.page()["items"]])

    def test_a_fresh_look_shows_everything_raised_since(self):
        """A snapshot is for one walk, not a freeze. No cursor means now."""
        self.make_ticket(subject="Already here")
        first = self.page()
        latecomer = self.make_ticket(subject="Raised while reading")

        fresh = self.page()
        self.assertEqual(fresh["total"], first["total"] + 1)
        self.assertEqual(fresh["items"][0]["id"], latecomer.pk)

    # ------------------------------------------------------- jumping vs walking

    def test_choosing_a_page_number_is_answered_from_a_fresh_snapshot(self):
        """Skipping to page three is the reader deciding to skip pages one and
        two, so there is no walk to keep faith with. One query at one instant
        cannot disagree with itself, which is what lets the footer keep its
        numbered buttons.
        """
        made = [self.make_ticket(subject=f"Ticket {i}") for i in range(9)]
        third = self.page(page=3, limit=3)

        self.assertEqual(len(third["items"]), 3)
        self.assertEqual(third["page"], 3)
        # The oldest three, since the newest sort first.
        self.assertEqual(
            [r["id"] for r in third["items"]],
            [t.pk for t in made[2::-1]],
        )

    def test_a_stale_snapshot_without_a_cursor_does_not_freeze_the_page(self):
        """A snapshot on its own would freeze the set for an offset, and an
        offset over a set that can shrink is the whole defect. Sent alone it
        is ignored rather than half-applied."""
        self.make_ticket(subject="Already here")
        first = self.page()
        self.make_ticket(subject="Raised while reading")

        self.assertEqual(self.page(asOf=first["asOf"])["total"], 2)

    # ----------------------------------------------------- the cursor on the wire

    def test_the_first_page_hands_out_both_halves_of_the_walk(self):
        self.make_ticket()
        data = self.page()
        self.assertIn("asOf", data)
        self.assertIsNotNone(data["after"])

    def test_an_empty_page_hands_out_no_cursor(self):
        """There is no last row to continue from, and inventing one would
        point the next request at something that does not exist."""
        self.assertIsNone(self.page()["after"])

    def test_the_stamp_is_handed_out_in_the_form_a_query_string_survives(self):
        """"+00:00" decodes to a space unless it was encoded.

        A stamp mangled that way parses as nothing, the snapshot silently
        stops applying, and every test that only checks "no row was lost"
        still passes, because not applying it loses no rows either. Handing
        out the "Z" form removes the trap at the source — for the cursor too,
        which carries a timestamp of its own.
        """
        self.make_ticket()
        data = self.page()
        self.assertTrue(data["asOf"].endswith("Z"))
        self.assertIn("Z_", data["after"])

    def test_a_space_where_a_plus_should_be_is_repaired(self):
        """Two tickets, not one. The first version of this test was a fake.

        With a single ticket in the fixture, a cursor that fails to parse and
        one that parses correctly both answer "one row" — so the broken case
        looked identical to the working one. It takes a second ticket for the
        repair to have anything to prove.
        """
        newer = self.make_ticket(subject="After the cursor")
        older = self.make_ticket(subject="Before the cursor")
        Ticket.objects.filter(pk=older.pk).update(
            support_updated_at=newer.support_updated_at - timedelta(hours=1)
        )
        first = self.page(limit=1)
        self.assertEqual([r["id"] for r in first["items"]], [newer.pk])

        data = self.page(
            limit=1,
            asOf=first["asOf"].replace("Z", "+00:00").replace("+", " "),
            after=first["after"].replace("Z", "+00:00").replace("+", " "),
        )

        self.assertEqual(
            [row["id"] for row in data["items"]], [older.pk],
            "the mangled stamp was not repaired, so the walk restarted",
        )

    def test_a_cursor_that_cannot_be_read_is_refused_out_loud(self):
        """Starting over instead would serve page one under a later page's
        number and lose every row the reader had not reached — quietly, which
        is the property this whole module exists to remove."""
        self.make_ticket()
        stamp_now = self.page()["asOf"]
        for bad in ("not-a-cursor", "_12", "2026-13-45T99:99:99Z_1", "abc_xyz"):
            with self.subTest(after=bad):
                response = self.client.get(QUEUE, {"after": bad, "asOf": stamp_now})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_cursor_without_its_snapshot_is_refused(self):
        """The cursor names a place inside one snapshot. Answering it against
        a set assembled a moment later is the two-requests-one-walk mistake
        arriving by a new door."""
        self.make_ticket()
        first = self.page()

        response = self.client.get(QUEUE, {"after": first["after"]})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_mangled_stamp_starts_a_fresh_snapshot_rather_than_failing(self):
        """Nonsense in asOf must not 500 or empty the queue mid-walk."""
        self.make_ticket()
        for bad in ("not-a-date", "", "2026-13-45T99:99:99Z"):
            with self.subTest(asOf=bad):
                self.assertEqual(self.page(asOf=bad)["total"], 1)


class AnalyticsWindowTests(AdminTicketAPITestCase):
    """The two date parameters: what they refuse, and what they include.

    Both halves were found by a full check rather than in review, and both
    are the kind a dashboard hides: one answers 500 to a string anybody can
    type, the other answers a confident wrong number.
    """

    ANALYTICS = f"{QUEUE}analytics/"

    def volume(self, **params):
        response = self.client.get(self.ANALYTICS, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return response.json()["data"]["demand"]["volume"]

    def test_an_impossible_date_is_refused_not_a_crash(self):
        """Two parsers, two shapes, and each raises on what the other rejects.

        parse_datetime returns None for "2026-02-30" and raises for
        "2026-13-45T00:00:00Z"; parse_date is the other way round. Guarding
        one of them leaves the other class of input answering 500, which is
        exactly what happened the first time.
        """
        impossible = [
            "2026-13-01",              # bare date, month out of range
            "2026-02-30",              # bare date, day out of range
            "2026-00-01",
            "9999-99-99",
            "2026-13-45T00:00:00Z",    # datetime, month and day out of range
            "2026-03-01T25:00:00Z",    # datetime, hour out of range
            "not-a-date",
        ]
        for value in impossible:
            for name in ("from", "to"):
                with self.subTest(value=value, parameter=name):
                    response = self.client.get(self.ANALYTICS, {name: value})
                    self.assertEqual(
                        response.status_code, status.HTTP_400_BAD_REQUEST,
                        f"{name}={value!r} answered {response.status_code}",
                    )

    def test_a_bare_to_date_includes_that_whole_day(self):
        """"To = the day it happened" must not report zero.

        The window is half-open, so a bare closing date has to become the
        start of the next day. Before that correction, a manager asking for
        "the 1st to today" got 0 and would read it as "nobody asked for help
        this month".
        """
        ticket = self.make_ticket()
        day = ticket.created_at.astimezone(dt_timezone.utc).date().isoformat()

        self.assertEqual(self.volume(**{"from": day, "to": day}), 1)

    def test_an_explicit_instant_is_taken_literally(self):
        """Somebody who typed a time meant that time.

        The whole-day correction applies to "2026-09-02" and must not apply
        to "2026-09-02T00:00:00Z", or a caller asking for a precise instant
        silently gets a day more than they asked for.
        """
        ticket = self.make_ticket()
        moment = ticket.created_at.astimezone(dt_timezone.utc)
        day = moment.date().isoformat()

        self.assertEqual(
            self.volume(**{"from": day, "to": f"{day}T00:00:00Z"}), 0,
        )


class IdParametersAgreeAcrossEndpointsTests(AdminTicketAPITestCase):
    """Two endpoints reading a row id from the query string must agree.

    They did not. The queue's ?assignee= refused a value past 2^63; the audit
    log's ?actor= stopped at int() and let it through, which answered 200 on
    PostgreSQL and 500 on SQLite — and SQLite is the one CI runs, so the
    stricter database was the one nobody was watching.
    """

    HUGE = "99999999999999999999999999"

    def endpoints(self):
        return [("queue", QUEUE, "assignee"), ("audit", f"{QUEUE}audit/", "actor")]

    def test_a_number_too_large_for_a_row_id_is_refused_by_both(self):
        for label, url, parameter in self.endpoints():
            with self.subTest(endpoint=label):
                response = self.client.get(url, {parameter: self.HUGE})
                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST,
                    f"{label} answered {response.status_code}",
                )

    def test_a_non_number_is_refused_by_both(self):
        for label, url, parameter in self.endpoints():
            with self.subTest(endpoint=label):
                response = self.client.get(url, {parameter: "nonsense"})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_real_id_still_works_on_both(self):
        for label, url, parameter in self.endpoints():
            with self.subTest(endpoint=label):
                response = self.client.get(url, {parameter: str(self.agent.pk)})
                self.assertEqual(response.status_code, status.HTTP_200_OK)


class SettingThePriorityItAlreadyHasDoesNothingTests(AdminTicketAPITestCase):
    """The mirror of the assignee guard, and it had no test either.

    Deleting the "is it actually different?" check on the priority branch left
    the whole backend suite green. Same three consequences as the assignee
    case: a noise row in the log people have to read, an inflated count, and
    the ticket lifted to the top of a queue nothing happened on.

    ⚠️ Measured, so nobody credits this with more than it does. The guard is
    written twice — once before the lock as an optimisation, once after it as
    the real check, because the committed value is the only one worth
    comparing. Deleting EITHER one on its own leaves these tests green, which
    is correct: the other still guards. Deleting BOTH turns them red.

    So this covers "the protection is gone", not "one of its two halves is
    gone". That is a property of redundant defences and not a weakness in the
    test; a single-mutation check on either line will survive, and reading
    that as a fake test would be the wrong conclusion.
    """

    def rows(self, ticket):
        return AuditLog.objects.filter(
            entity_type="ticket", entity_id=ticket.pk, action="priority"
        ).count()

    def test_no_audit_row_and_no_clock_move(self):
        ticket = self.make_ticket()
        self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            data=json.dumps({"priority": TicketPriority.HIGH}),
            content_type="application/json",
        )
        ticket.refresh_from_db()
        before_rows = self.rows(ticket)
        before_clock = ticket.support_updated_at

        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            data=json.dumps({"priority": TicketPriority.HIGH}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(self.rows(ticket), before_rows, "wrote a high -> high row")
        self.assertEqual(ticket.support_updated_at, before_clock)

    def test_a_real_change_still_records(self):
        ticket = self.make_ticket()
        before = self.rows(ticket)

        self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            data=json.dumps({"priority": TicketPriority.LOW}),
            content_type="application/json",
        )

        self.assertEqual(self.rows(ticket), before + 1)


class APatchEitherHappensOrItDoesNotTests(AdminTicketAPITestCase):
    """priority and status may arrive in one request. They used to commit
    separately.

    The priority write landed in its own transaction; the status write then
    found the ticket deleted and the view answered 404 "Ticket not found".
    The caller reads that as "nothing happened", while the priority change is
    in the database with an audit row for it.
    """

    def test_a_ticket_deleted_mid_request_leaves_no_half_applied_change(self):
        ticket = self.make_ticket()
        original = ticket.priority

        real_set_status = lifecycle.set_status

        def delete_then_set_status(**kwargs):
            # Stands in for another admin deleting the ticket in the gap
            # between the two writes. Deleting through the service so the row
            # ends up in exactly the state the real race produces.
            lifecycle.soft_delete(ticket=Ticket.objects.get(pk=ticket.pk),
                                  actor=self.agent)
            return real_set_status(**kwargs)

        with patch.object(lifecycle, "set_status", side_effect=delete_then_set_status):
            response = self.client.patch(
                f"{QUEUE}{ticket.pk}/",
                data=json.dumps({
                    "priority": TicketPriority.HIGH,
                    "status": TicketStatus.RESOLVED,
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        ticket.refresh_from_db()
        self.assertEqual(
            ticket.priority, original,
            "the request answered 'not found' and changed the priority anyway",
        )
        self.assertFalse(
            AuditLog.objects.filter(
                entity_type="ticket", entity_id=ticket.pk, action="priority"
            ).exists(),
            "an audit row survived for a change the caller was told never happened",
        )

    def test_both_fields_still_apply_when_nothing_goes_wrong(self):
        """The guard must not have cost the ordinary case."""
        ticket = self.make_ticket()

        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/",
            data=json.dumps({
                "priority": TicketPriority.HIGH,
                "status": TicketStatus.RESOLVED,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.priority, TicketPriority.HIGH)
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)


class RevokingOnTheRosterStaysRevokedTests(AdminTicketAPITestCase):
    """The reported round trip, end to end over HTTP.

    An admin revokes queue access on the roster page, and it works: the row is
    gone and the queue answers 403. Then somebody corrects that person's
    surname on the People page — an edit with nothing to do with permissions —
    and the access came back, with no audit row naming anyone. The last
    support_scope event on record stayed "delete", so the audit trail said the
    person had no access while they were reading tickets.

    The revoke endpoint does not touch the role on purpose: the roster page
    grants access to accounts whose role is something else entirely. So the
    role still reads "support" afterwards, and it is `update_user` that must
    not treat a save as a fresh grant.
    """

    def setUp(self):
        super().setUp()
        self.role_support, _ = Roles.objects.get_or_create(role_name="support")
        RoleAssignmentHistory.objects.create(
            user=self.agent, role=self.role_support, valid_from=timezone.now()
        )
        self.client.force_login(self.admin)

    def people_page_save_of_the_surname(self, surname):
        """What adminweb sends when an admin edits only the last name.

        It round-trips every field the editor holds, `role` included, which is
        why a save can look like a role change to code reading the raw string.
        """
        return self.client.put(
            f"/api/v1/admin/user/{self.agent.pk}/",
            {
                "firstName": self.agent.first_name,
                "lastName": surname,
                "role": "support",
            },
            format="json",
        )

    def test_an_unrelated_save_does_not_hand_the_queue_back(self):
        revoked = self.client.delete(f"{QUEUE}support-scope/{self.agent.pk}/")
        self.assertEqual(revoked.status_code, status.HTTP_200_OK)
        self.assertFalse(SupportScope.objects.filter(user=self.agent).exists())

        saved = self.people_page_save_of_the_surname("Reid-Okafor")
        self.assertEqual(saved.status_code, status.HTTP_200_OK, saved.content)

        self.assertFalse(
            SupportScope.objects.filter(user=self.agent).exists(),
            "an unrelated People page save undid a deliberate revocation",
        )
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(QUEUE).status_code, status.HTTP_403_FORBIDDEN)

    def test_the_audit_trail_matches_what_actually_happened(self):
        self.client.delete(f"{QUEUE}support-scope/{self.agent.pk}/")
        self.people_page_save_of_the_surname("Reid-Okafor")

        events = list(
            AuditLog.objects.filter(
                entity_type="support_scope", entity_id=self.agent.pk
            ).order_by("id").values_list("action", flat=True)
        )
        self.assertEqual(events, ["delete"])


class GrantingQueueAccessToAStudentIsRefusedTests(AdminTicketAPITestCase):
    """The guard rail beside the roster page's Grant button.

    Not a permission hole: the endpoint is admin-only and the grant is a
    deliberate click. It is that the click has nothing to catch it. The
    candidate rows show a name and an email and no role — the search endpoint
    returns one and the page drops it — and Grant fires straight away, while
    Revoke next to it asks for confirmation. One wrong row and a student
    account is reading every ticket on the platform: other students' names,
    email addresses, and whatever they wrote about their problem.
    """

    def setUp(self):
        super().setUp()
        self.student_role, _ = Roles.objects.get_or_create(role_name="student")
        self.mentor_role, _ = Roles.objects.get_or_create(role_name="mentor")
        self.client.force_login(self.admin)

    def with_role(self, user, role):
        RoleAssignmentHistory.objects.create(
            user=user, role=role, valid_from=timezone.now()
        )
        return user

    def grant(self, user):
        return self.client.post(f"{QUEUE}support-scope/", {"userId": user.pk})

    def test_a_student_account_is_refused(self):
        student = self.with_role(self.requester, self.student_role)

        response = self.grant(student)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SupportScope.objects.filter(user=student).exists())

    def test_the_refusal_says_what_to_do_about_it(self):
        student = self.with_role(self.requester, self.student_role)

        message = self.grant(student).json()["msg"]

        self.assertIn("Students cannot", message)
        self.assertIn("Change their role first", message)

    def test_a_capitalised_student_role_is_refused_too(self):
        """roles.role_name is free text with a case-sensitive unique index, so
        "Student" and "student" are two rows and this platform has both. A
        guard comparing strings would let the capitalised one through."""
        capitalised, _ = Roles.objects.get_or_create(role_name="Student")
        student = self.with_role(self.requester, capitalised)

        self.assertEqual(self.grant(student).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SupportScope.objects.filter(user=student).exists())

    def test_someone_holding_a_student_role_among_others_is_refused(self):
        """Two active role rows is a real state on this platform.

        Student is added first and mentor second on purpose: "the most recent
        active role" would answer mentor here and let the grant through, and
        that reading is one helper call away in this codebase. Any of the
        person's active roles being student has to be enough, because it is the
        student half that must not read other students' tickets.
        """
        person = self.with_role(self.requester, self.student_role)
        self.with_role(person, self.mentor_role)

        self.assertEqual(self.grant(person).status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_mentor_can_still_be_granted(self):
        """The roster page exists to do exactly this — the client's own route
        for handing queue access to somebody who already has an account."""
        mentor = self.with_role(self.outsider, self.mentor_role)

        response = self.grant(mentor)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertTrue(SupportScope.objects.filter(user=mentor).exists())

    def test_an_account_with_no_role_row_can_still_be_granted(self):
        """Every existing test in this file grants one of these, and a platform
        this old has accounts that predate the roles table."""
        response = self.grant(self.outsider)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)


class AnalyticsWindowExtremeDatesTests(AdminTicketAPITestCase):
    """Dates that parse cleanly and then fall off the end of the calendar.

    The sweep in AnalyticsWindowTests is all malformed values, and every one
    of them dies in the parser without reaching the window arithmetic. These
    are the other class: well formed, accepted, and out of range only after
    that arithmetic runs.

    Two shapes, and they fail in two different places. "to=9999-12-31" is the
    loud one: the half-open correction adds a day to the last day datetime can
    hold, so _window_bound itself raises. The quiet one is an offset, which
    moves the instant when it is read as UTC and so falls off either end
    without _window_bound noticing. That one used to reach the database layer
    and 500 from there, out of a value this endpoint had already accepted.

    Generated rather than listed, because a hand-written list is how the first
    draft of this covered only the loud shape. Every value in that list looked
    extreme, and every one of them was already handled.
    """

    ANALYTICS = f"{QUEUE}analytics/"

    def statuses(self, value):
        return {
            name: self.client.get(self.ANALYTICS, {name: value}).status_code
            for name in ("from", "to")
        }

    def test_no_calendar_extreme_answers_a_server_error(self):
        from itertools import product

        values = []
        for year, month, day in product(
            ("0001", "9999"), ("01", "12"), ("01", "31")
        ):
            values.append(f"{year}-{month}-{day}")
            for clock, offset in product(
                ("T00:00:00", "T23:59:59"), ("Z", "+14:00", "-12:00")
            ):
                values.append(f"{year}-{month}-{day}{clock}{offset}")

        for value in values:
            for name, code in self.statuses(value).items():
                with self.subTest(value=value, parameter=name):
                    self.assertIn(
                        code,
                        (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                        f"{name}={value} answered {code}",
                    )

    def test_the_last_day_there_is_gets_a_400(self):
        """9999-12-31 is datetime.max's date, so the whole-day correction has
        nowhere to go. The reader has to be told that, not handed a 500."""
        self.assertEqual(
            self.statuses("9999-12-31")["to"], status.HTTP_400_BAD_REQUEST
        )

    def test_an_offset_that_carries_it_past_the_end_gets_a_400(self):
        """The quiet half. This one is inside range as typed and outside it as
        UTC, so nothing on the way in objects to it."""
        for value in ("9999-12-31T23:59:59-12:00", "0001-01-01T00:00:00+14:00"):
            with self.subTest(value=value):
                self.assertEqual(
                    self.statuses(value),
                    {"from": status.HTTP_400_BAD_REQUEST,
                     "to": status.HTTP_400_BAD_REQUEST},
                )

    def test_the_day_before_the_end_still_works(self):
        """The refusal has to stop at the values that genuinely cannot be
        represented. One day earlier is an ordinary window."""
        self.assertEqual(self.statuses("9999-12-30")["to"], status.HTTP_200_OK)

    def test_an_offset_window_is_reported_back_in_utc(self):
        """What the docstring on _window_bound has always promised, and what
        the normalisation added for the offset case now actually does."""
        data = self.client.get(
            self.ANALYTICS, {"from": "2026-03-01T00:00:00+11:00"}
        ).json()["data"]

        self.assertEqual(data["window"]["from"], "2026-02-28T13:00:00+00:00")


class GrantingQueueAccessToASwitchedOffAccountTests(AdminTicketAPITestCase):
    """The other guard rail beside the Grant button.

    A deactivated account cannot sign in, so the grant does nothing on the
    day it is made. It is not harmless: the row is a standing decision, and
    reactivating the account turns it into access to every ticket on the
    platform with nobody deciding that a second time.

    Deliberately narrower than is_active. "Invited" and "pending" accounts are
    is_active=False too, and pre-granting to somebody who has been invited but
    has not finished onboarding is a thing an admin may reasonably do.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def grant(self, user):
        return self.client.post(f"{QUEUE}support-scope/", {"userId": user.pk})

    def test_a_deactivated_account_is_refused(self):
        self.outsider.deactivate()

        response = self.grant(self.outsider)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SupportScope.objects.filter(user=self.outsider).exists())

    def test_a_suspended_account_is_refused(self):
        self.outsider.suspend()

        response = self.grant(self.outsider)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SupportScope.objects.filter(user=self.outsider).exists())

    def test_the_refusal_says_what_to_do_about_it(self):
        self.outsider.deactivate()

        message = self.grant(self.outsider).json()["msg"]

        self.assertEqual(
            message,
            "This account is switched off, so it cannot work the queue. "
            "Reactivate it first, then grant support access.",
        )

    def test_an_invited_account_can_still_be_granted(self):
        """is_active is False here as well, and this one has to go through.
        Handing queue access to a new colleague before they have finished
        setting their password is ordinary."""
        self.outsider.invite()

        response = self.grant(self.outsider)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertTrue(SupportScope.objects.filter(user=self.outsider).exists())

    def test_the_roster_says_which_rows_are_switched_off(self):
        """The half a grant guard cannot fix. Deactivating somebody who is
        already on the roster leaves their row exactly where it was, which is
        deliberate. Until this field, the screen had no way to tell that row
        apart from an agent who is working today.
        """
        self.agent.deactivate()

        rows = self.client.get(f"{QUEUE}support-scope/").json()["data"]
        row = next(r for r in rows if r["id"] == self.agent.pk)

        self.assertEqual(row["accountStatus"], "deactivated")

    def test_the_roster_says_so_for_a_working_agent_too(self):
        rows = self.client.get(f"{QUEUE}support-scope/").json()["data"]
        row = next(r for r in rows if r["id"] == self.agent.pk)

        self.assertEqual(row["accountStatus"], "active")


class BulkHandBackToThePoolTests(AdminTicketAPITestCase):
    """Bulk assign has to be able to say "nobody", the way the PATCH can.

    An agent who swept twenty tickets onto themselves by mistake had one way
    back: twenty separate PATCHes. Nothing below the serializer needed that.
    bulk_assign hands the value straight to the same _assign_one the PATCH
    uses, and that has always accepted None.
    """

    def bulk(self, ticket_ids, assignee_id):
        return self.client.post(
            f"{QUEUE}bulk-assign/",
            {"ticketIds": ticket_ids, "assigneeId": assignee_id},
            format="json",
        )

    def test_a_batch_goes_back_to_the_pool(self):
        tickets = [self.make_ticket(subject=f"Swept {i}") for i in range(3)]
        for ticket in tickets:
            lifecycle.claim(ticket=ticket, actor=self.agent)

        response = self.bulk([t.pk for t in tickets], None)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertTrue(all(r["ok"] for r in response.json()["data"]["results"]))
        for ticket in tickets:
            ticket.refresh_from_db()
            self.assertIsNone(ticket.assignee_id)

    def test_handing_a_batch_back_leaves_the_statuses_alone(self):
        """Same rule the batch already follows for a real assignee: sweeping
        "pending user" back into "in progress" would erase the fact that the
        ball is not ours."""
        waiting = self.make_ticket(subject="Waiting on them")
        lifecycle.claim(ticket=waiting, actor=self.agent)
        lifecycle.set_status(
            ticket=waiting, actor=self.agent, new_status=TicketStatus.PENDING_USER
        )

        self.bulk([waiting.pk], None)

        waiting.refresh_from_db()
        self.assertIsNone(waiting.assignee_id)
        self.assertEqual(waiting.status, TicketStatus.PENDING_USER)

    def test_leaving_the_field_out_is_still_a_400(self):
        """allow_null is not the same as optional. A batch with no assigneeId
        at all is a client bug, and answering 200 to it would quietly unassign
        whatever was selected."""
        ticket = self.make_ticket()

        response = self.client.post(
            f"{QUEUE}bulk-assign/", {"ticketIds": [ticket.pk]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AssigningToSomebodyWhoCannotWorkTheQueueTests(AdminTicketAPITestCase):
    """The refusal has to name the reason it refused.

    Both assignee fields validate against support_capable_users(), and DRF's
    default message for a filtered queryset says the object does not exist.
    That is true of an id nobody owns and false of what actually happens: a
    present, working account that has no support access. A caller reading the
    default goes looking for a deleted row.

    The admin app never shows the string. Anything else that talks to this API
    does.
    """

    EXPECTED = (
        'Cannot assign to user "{pk}". They need an active account with '
        'support queue access.'
    )

    def test_bulk_assign_says_why(self):
        ticket = self.make_ticket()

        response = self.client.post(
            f"{QUEUE}bulk-assign/",
            {"ticketIds": [ticket.pk], "assigneeId": self.outsider.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json()["fields"]["assigneeId"],
            [self.EXPECTED.format(pk=self.outsider.pk)],
        )

    def test_the_single_ticket_patch_says_the_same_thing(self):
        """The endpoint the original report missed. One message, two doors."""
        ticket = self.make_ticket()

        response = self.client.patch(
            f"{QUEUE}{ticket.pk}/", {"assignee": self.outsider.pk}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json()["fields"]["assignee"],
            [self.EXPECTED.format(pk=self.outsider.pk)],
        )

    def test_an_id_nobody_owns_gets_the_same_answer(self):
        """Not a compromise, a decision. Telling the caller apart from the
        outside which of the two it was would answer "does this user id
        exist?" for anybody who can reach the queue."""
        ticket = self.make_ticket()
        missing = self.outsider.pk + 10_000

        response = self.client.post(
            f"{QUEUE}bulk-assign/",
            {"ticketIds": [ticket.pk], "assigneeId": missing},
            format="json",
        )

        self.assertEqual(
            response.json()["fields"]["assigneeId"],
            [self.EXPECTED.format(pk=missing)],
        )

    def test_somebody_who_can_work_the_queue_is_still_accepted(self):
        ticket = self.make_ticket()

        response = self.client.post(
            f"{QUEUE}bulk-assign/",
            {"ticketIds": [ticket.pk], "assigneeId": self.agent.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)


class PageSizeOverTheCapIsReportedTests(AdminTicketAPITestCase):
    """Clamping is deliberate. Saying so in the response is the other half.

    Asking for more than the cap gets fewer rows rather than an error
    (04-api-contract §3, DEC-016⑩). A client that then works its page count
    out from the limit it *asked* for gets a count that is too small, and on a
    screen with no "next page anyway" fallback the rows past the cap become
    unreachable.

    Nothing here can fix that on its own. What it pins is the two values a
    client needs in order to get it right: the limit that was actually used,
    and whether anything is left behind the page.

    100 is written out rather than imported from views.MAX_PAGE_SIZE on
    purpose. Importing the constant would make this agree with whatever the
    code says, including a change nobody meant to make.
    """

    CAP = 100

    def test_the_queue_echoes_the_limit_it_used_not_the_one_asked_for(self):
        self.make_ticket()

        data = self.client.get(QUEUE, {"limit": 200}).json()["data"]

        self.assertEqual(data["limit"], self.CAP)

    def test_the_queue_says_there_is_more_behind_a_clamped_page(self):
        for i in range(self.CAP + 1):
            self.make_ticket(subject=f"Bulk {i}")

        data = self.client.get(QUEUE, {"limit": 200}).json()["data"]

        self.assertEqual(len(data["items"]), self.CAP)
        self.assertEqual(data["total"], self.CAP + 1)
        self.assertTrue(data["hasMore"], "the clamped page claimed to be the last")

    def audit_rows(self, count):
        """Log rows written straight to the table.

        101 trips through soft_delete would raise 101 tickets first, allocate
        101 numbers and queue 101 emails, none of which this is about. What is
        being paged here is the log.
        """
        AuditLog.objects.bulk_create([
            AuditLog(
                actor_user=self.admin,
                entity_type=lifecycle.AUDIT_ENTITY_TYPE,
                entity_id=index + 1,
                action=AuditLog.ActionChoices.UPDATE,
                before_state={"status": "open"},
                after_state={"status": "in_progress"},
            )
            for index in range(count)
        ])

    def test_the_audit_log_reports_the_same_two_things(self):
        """The audit screen is the one with no fallback: it works its page
        count out from total and limit alone, so these two values are the only
        way it can know it is not showing everything."""
        for i in range(3):
            lifecycle.soft_delete(ticket=self.make_ticket(subject=f"Gone {i}"),
                                  actor=self.admin)

        data = self.client.get(f"{QUEUE}audit/", {"limit": 500}).json()["data"]

        self.assertEqual(data["limit"], self.CAP)
        self.assertFalse(data["hasMore"])

    def test_the_audit_log_says_there_is_more_behind_a_clamped_page(self):
        """The direction that hides rows, and the one the case above cannot see.

        Three log rows fit on one page, so False is the right answer there and
        a hasMore wired to the constant False passes it. False is also the only
        harmful value on this screen: it has no "next page anyway" fallback, so
        a page that says it is the last one is the last one the reader can
        reach. This is the queue case above, mirrored onto the endpoint that
        needs it more.
        """
        self.audit_rows(self.CAP + 1)

        data = self.client.get(f"{QUEUE}audit/", {"limit": 500}).json()["data"]

        self.assertEqual(data["limit"], self.CAP)
        self.assertEqual(len(data["items"]), self.CAP)
        self.assertEqual(data["total"], self.CAP + 1)
        self.assertTrue(data["hasMore"], "the clamped audit page claimed to be the last")

        # And the other end of the same walk. hasMore has to count the rows
        # already passed, not only the ones on this page, or the last page
        # offers a next page that is empty.
        last = self.client.get(f"{QUEUE}audit/", {"limit": 500, "page": 2}).json()["data"]

        self.assertEqual(len(last["items"]), 1)
        self.assertFalse(last["hasMore"], "the last audit page offered another one")


class SupportMessagesAreRateLimitedTooTests(AdminTicketAPITestCase):
    """The second door into the same room.

    The requester's reply endpoint and this one both write their attachments
    through stored_attachments. Capping only the first would have been a lock
    on one of two doors, which is the shape of defect this module has already
    shipped once.
    """

    def note(self, ticket):
        return self.client.post(
            f"{QUEUE}{ticket.pk}/messages/",
            {"body": "Checked their account.", "messageType": "internal_note"},
        )

    def test_a_loop_of_internal_notes_is_stopped(self):
        from apps.tickets.views import MessageWriteThrottle

        ticket = self.make_ticket()
        with patch.object(MessageWriteThrottle, "rate", "2/hour"):
            cache.clear()
            codes = [self.note(ticket).status_code for _ in range(3)]

        self.assertEqual(
            codes,
            [
                status.HTTP_201_CREATED,
                status.HTTP_201_CREATED,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )

    def test_reading_the_queue_is_not_touched_by_it(self):
        """An agent who has just hit the cap still has to be able to see the
        work in front of them."""
        from apps.tickets.views import MessageWriteThrottle

        ticket = self.make_ticket()
        with patch.object(MessageWriteThrottle, "rate", "1/hour"):
            cache.clear()
            self.note(ticket)
            self.assertEqual(
                self.note(ticket).status_code, status.HTTP_429_TOO_MANY_REQUESTS
            )

            self.assertEqual(self.client.get(QUEUE).status_code, status.HTTP_200_OK)
