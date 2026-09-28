"""The p52 dashboard numbers, asserted against a hand-built set of tickets.

Time is pinned by passing ``now`` into the service rather than by freezing the
clock: freezegun is not in requirements.txt, and the two functions that need a
reference time already take one so the queue and the dashboard can be asked
about the same instant.

Timestamps are written with .update() rather than by living through the
events, because created_at and resolved_at are default=now columns — setting
them any other way means sleeping in a test.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.groups.models import Countries
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
    TicketChannel,
    TicketStatus,
)
from apps.tickets.services import analytics, lifecycle

User = get_user_model()

NOW = datetime(2026, 3, 15, 12, 0, tzinfo=dt_timezone.utc)


def hours(n):
    return timedelta(hours=n)


class AnalyticsTestCase(TestCase):
    def setUp(self):
        self.australia = Countries.objects.create(country_name="Australia")
        self.student_role = Roles.objects.create(role_name="Student")

        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson", country=self.australia,
        )
        RoleAssignmentHistory.objects.create(
            user=self.requester, role=self.student_role, valid_from=NOW - hours(720),
        )
        self.other = User.objects.create_user(
            email="bruno@example.com", password="pass1234",
            first_name="Bruno", last_name="Silva",
        )
        self.agent = User.objects.create_user(
            email="agent@example.com", password="pass1234",
            first_name="Sam", last_name="Reid",
        )
        SupportScope.objects.create(user=self.agent)

    def make(self, *, owner=None, created=None, **fields):
        ticket = lifecycle.create_ticket(
            user=owner or self.requester,
            category=fields.pop("category", TicketCategory.HELP_STUDENT_GROUP),
            subject="Cannot access group workspace",
            body="I get an error opening my group.",
        )
        stamps = {}
        if created is not None:
            stamps["created_at"] = created
        stamps.update(fields)
        if stamps:
            Ticket.objects.filter(pk=ticket.pk).update(**stamps)
            ticket.refresh_from_db()
        return ticket


class DemandTests(AnalyticsTestCase):
    def test_volume_and_the_two_mixes(self):
        self.make()
        self.make()
        self.make(category=TicketCategory.ACCOUNT_ACCESS)
        self.make(channel=TicketChannel.AI_SCREENING)

        result = analytics.analytics(now=NOW)
        self.assertEqual(result["demand"]["volume"], 4)
        self.assertEqual(
            result["demand"]["categoryMix"],
            [
                {"value": TicketCategory.HELP_STUDENT_GROUP, "count": 3},
                {"value": TicketCategory.ACCOUNT_ACCESS, "count": 1},
            ],
        )
        self.assertEqual(
            result["demand"]["channelMix"],
            [
                {"value": TicketChannel.PORTAL, "count": 3},
                {"value": TicketChannel.AI_SCREENING, "count": 1},
            ],
        )

    def test_a_deleted_ticket_is_not_demand(self):
        kept = self.make()
        binned = self.make()
        lifecycle.soft_delete(ticket=binned, actor=self.agent)

        self.assertEqual(analytics.analytics(now=NOW)["demand"]["volume"], 1)
        self.assertEqual(kept.pk, kept.pk)  # keeps the name meaningful


class FlowTests(AnalyticsTestCase):
    def test_unassigned_backlog_excludes_resolved(self):
        self.make()
        owned = self.make()
        lifecycle.claim(ticket=owned, actor=self.agent)
        done = self.make()
        lifecycle.resolve(ticket=done, actor=self.agent)

        # Resolved tickets have no owner either, but nobody has to pick them up.
        self.assertEqual(analytics.analytics(now=NOW)["flow"]["unassignedBacklog"], 1)

    def test_age_by_status_measures_time_since_the_last_support_activity(self):
        self.make(support_updated_at=NOW - hours(48))
        self.make(support_updated_at=NOW - hours(24))

        buckets = analytics.analytics(now=NOW)["flow"]["ageByStatus"]
        row = next(b for b in buckets if b["status"] == TicketStatus.OPEN)
        self.assertEqual(row["averageSeconds"], int(hours(36).total_seconds()))

    def test_reopens_are_counted_per_event_not_per_ticket(self):
        ticket = self.make()
        for _ in range(2):
            lifecycle.resolve(ticket=ticket, actor=self.agent)
            lifecycle.add_user_reply(
                ticket=ticket, user=self.requester, body="Still broken."
            )

        self.assertEqual(analytics.analytics(now=NOW)["flow"]["reopens"], 2)

    def test_picking_up_a_ticket_is_not_a_hand_off(self):
        """Both write an audit row with action=assign. Counting the pick-up
        would make every ticket look like it was passed around once.
        """
        ticket = self.make()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        self.assertEqual(analytics.analytics(now=NOW)["flow"]["handOffs"], 0)

    def test_passing_a_ticket_on_is(self):
        ticket = self.make()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        colleague = User.objects.create_user(
            email="dana@example.com", password="pass1234", first_name="Dana",
        )
        SupportScope.objects.create(user=colleague)
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=colleague)

        self.assertEqual(analytics.analytics(now=NOW)["flow"]["handOffs"], 1)


class ServiceTests(AnalyticsTestCase):
    def test_average_first_response_and_resolution_time(self):
        a = self.make(created=NOW - hours(10))
        Ticket.objects.filter(pk=a.pk).update(
            status=TicketStatus.RESOLVED,
            first_response_at=NOW - hours(8), resolved_at=NOW - hours(5),
        )
        b = self.make(created=NOW - hours(10))
        Ticket.objects.filter(pk=b.pk).update(
            status=TicketStatus.RESOLVED,
            first_response_at=NOW - hours(6), resolved_at=NOW - hours(2),
        )
        # Never answered: must not drag the average towards zero.
        self.make(created=NOW - hours(10))

        service = analytics.analytics(now=NOW)["service"]
        # (2h + 4h) / 2
        self.assertEqual(service["firstResponseSeconds"], int(hours(3).total_seconds()))
        self.assertEqual(service["answeredCount"], 2)
        # (5h + 8h) / 2
        self.assertEqual(
            service["resolutionSeconds"], int(timedelta(hours=6, minutes=30).total_seconds())
        )
        self.assertEqual(service["resolvedCount"], 2)

    def test_overdue_uses_the_same_predicate_as_the_queue_badge(self):
        """Normal priority is a 24 hour window, measured from when the ball
        last landed with support — not from when the ticket was raised, and
        not from whether it has ever been answered.

        The dashboard and the queue call the same function
        (services.queue.overdue_condition) precisely so they cannot disagree.
        A second copy of the rule here would be one refactor away from the
        dashboard reporting a different number from the card an agent is
        looking at.
        """
        self.make(created=NOW - hours(48), awaiting_support_since=NOW - hours(48))
        # Answered: the clock is stopped, so age no longer matters.
        self.make(created=NOW - hours(48), awaiting_support_since=None)
        # With support, but only just.
        self.make(created=NOW - hours(2), awaiting_support_since=NOW - hours(2))

        self.assertEqual(analytics.analytics(now=NOW)["service"]["overdue"], 1)

    def test_a_ticket_answered_once_can_be_overdue_again(self):
        """The change the client asked for on 2026-09-04, seen from the
        dashboard. ``first_response_at`` is set, which under the old rule made
        a ticket permanently safe; the clock is what decides now."""
        self.make(
            created=NOW - hours(72),
            first_response_at=NOW - hours(60),
            awaiting_support_since=NOW - hours(48),
        )
        self.assertEqual(analytics.analytics(now=NOW)["service"]["overdue"], 1)


class QualityTests(AnalyticsTestCase):
    def test_resolution_rate(self):
        for _ in range(3):
            self.make()
        done = self.make()
        lifecycle.resolve(ticket=done, actor=self.agent)

        quality = analytics.analytics(now=NOW)["quality"]
        self.assertEqual(quality["resolutionRate"], 0.25)
        self.assertEqual(quality["resolvedCount"], 1)
        self.assertEqual(quality["totalCount"], 4)

    def test_resolution_rate_is_null_not_zero_when_there_is_nothing(self):
        """Zero percent resolved is a damning number to report for an empty
        window.
        """
        self.assertIsNone(analytics.analytics(now=NOW)["quality"]["resolutionRate"])

    def test_repeat_contact_counts_people_not_tickets(self):
        for _ in range(3):
            self.make()
        self.make(owner=self.other)

        # One person raised three, one raised one: one repeat contact.
        self.assertEqual(analytics.analytics(now=NOW)["quality"]["repeatContacts"], 1)

    def test_satisfaction_says_it_is_not_collected(self):
        self.make()
        quality = analytics.analytics(now=NOW)["quality"]
        self.assertIsNone(quality["satisfaction"])
        self.assertFalse(quality["satisfactionAvailable"])


class TheTwoResolvedCountsCannotDisagreeTests(AnalyticsTestCase):
    """The dashboard puts two "resolved" numbers on one screen.

    Both have to be the same number or the client asks which one is real, and
    a seeded demo database once showed 15 next to 13.

    Two things keep them together, and they are tested separately because
    each answers a different question. Both counts read the status column, so
    they agree on any row whatever, including rows no service call can write.
    And the lifecycle never leaves a resolution date on a ticket that is not
    resolved, which is what keeps that date out of the average service()
    reports beside its count.
    """

    def assertCountsAgree(self, where):
        payload = analytics.analytics(now=NOW)
        self.assertEqual(
            payload["service"]["resolvedCount"],
            payload["quality"]["resolvedCount"],
            f"two different resolved counts after {where}",
        )

    def test_every_status_transition_from_the_dropdown_keeps_the_date_with_the_status(self):
        """Walked rather than listed: every ordered pair of statuses is driven
        through the dropdown. A hand-picked list of interesting transitions is
        how the eighth one gets missed."""
        ticket = self.make()
        for before in TicketStatus.values:
            for after in TicketStatus.values:
                if before == after:
                    continue
                for target in (before, after):
                    with self.subTest(before=before, after=after, at=target):
                        lifecycle.set_status(
                            ticket=ticket, new_status=target, actor=self.agent
                        )
                        ticket.refresh_from_db()
                        self.assertEqual(
                            ticket.resolved_at is not None,
                            ticket.status == TicketStatus.RESOLVED,
                            f"{ticket.status} carries resolved_at={ticket.resolved_at}",
                        )
                        self.assertCountsAgree(f"set_status -> {target}")

    def test_a_requesters_reply_on_a_resolved_ticket_takes_the_date_with_it(self):
        """reopen() is the requester's door, not the dropdown's."""
        ticket = self.make()
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.resolved_at)
        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="Still broken."
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertIsNone(ticket.resolved_at)
        self.assertCountsAgree("the requester's reply reopening it")

    def test_a_reply_that_moves_a_resolved_ticket_to_pending_takes_it_too(self):
        """The third writer of resolved_at: one action that replies and moves
        the ticket in the same transaction."""
        ticket = self.make()
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        lifecycle.add_support_reply(
            ticket=ticket,
            actor=self.agent,
            body="One more thing before we close this.",
            move_to_pending=True,
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        self.assertIsNone(ticket.resolved_at)
        self.assertCountsAgree("reply and move to pending on a resolved ticket")

    def test_no_row_written_straight_into_the_table_can_split_them(self):
        """The belt to the lifecycle's braces, and the one the demo database
        needed. A seeding script wrote a resolution date onto tickets it left
        in progress, which no service call can produce, and the two cards
        disagreed by exactly those two tickets.

        Every combination of the two columns is written, rather than the one
        combination the demo database happened to hold. The first attempt at
        this counted the status and the date together. That closed the
        combination the demo database had, and left the mirror of it open: a
        ticket resolved with no date still split the pair.
        """
        ticket = self.make()
        for status in TicketStatus.values:
            for resolved_at in (NOW - hours(5), None):
                with self.subTest(status=status, resolved_at=resolved_at):
                    Ticket.objects.filter(pk=ticket.pk).update(
                        status=status, resolved_at=resolved_at
                    )
                    payload = analytics.analytics(now=NOW)
                    counted = 1 if status == TicketStatus.RESOLVED else 0
                    self.assertEqual(payload["quality"]["resolvedCount"], counted)
                    self.assertEqual(payload["service"]["resolvedCount"], counted)
                    # A date on a ticket that is not resolved is not a
                    # resolution time either, so it stays out of the average.
                    self.assertEqual(
                        payload["service"]["resolutionSeconds"] is not None,
                        counted == 1 and resolved_at is not None,
                        f"resolutionSeconds={payload['service']['resolutionSeconds']}",
                    )


class SegmentTests(AnalyticsTestCase):
    def test_every_advertised_dimension_can_actually_be_segmented(self):
        """Guards the gap between the list the API advertises and the columns
        it can group by.
        """
        self.make()
        for dimension in analytics.analytics(now=NOW)["dimensions"]:
            with self.subTest(dimension=dimension):
                result = analytics.analytics(dimension=dimension, now=NOW)
                self.assertEqual(result["segment"]["dimension"], dimension)
                self.assertTrue(result["segment"]["buckets"])

    def test_user_type_reads_the_snapshot_not_a_live_join(self):
        """The requester's role is frozen on the ticket, so a promotion does
        not silently re-label a year of history.
        """
        self.make()
        RoleAssignmentHistory.objects.filter(user=self.requester).update(
            valid_to=NOW - hours(1)
        )
        mentor = Roles.objects.create(role_name="Mentor")
        RoleAssignmentHistory.objects.create(
            user=self.requester, role=mentor, valid_from=NOW,
        )

        buckets = analytics.analytics(dimension="userType", now=NOW)["segment"]["buckets"]
        self.assertEqual(buckets, [{"value": "Student", "count": 1}])

    def test_a_ticket_raised_before_the_column_existed_has_an_empty_bucket(self):
        ticket = self.make()
        Ticket.objects.filter(pk=ticket.pk).update(requester_role="")

        buckets = analytics.analytics(dimension="userType", now=NOW)["segment"]["buckets"]
        self.assertEqual(buckets, [{"value": "", "count": 1}])

    def test_an_unowned_ticket_segments_as_the_empty_bucket(self):
        """assignee is the one nullable column here. Reported as "" so the
        front end has one no-value case rather than two.
        """
        self.make()
        buckets = analytics.analytics(dimension="assignee", now=NOW)["segment"]["buckets"]
        self.assertEqual(buckets, [{"value": "", "count": 1}])

    def test_an_owned_ticket_segments_as_a_string_not_a_number(self):
        """assignee segments on a FK id, which is an integer in the database.

        The client declares every bucket value as a string and parses the
        whole payload in one go, so a single owned ticket in the window used
        to fail validation and blank the entire dashboard — not just this
        chart. Asserted on the type, because an integer id renders perfectly
        well in a chart and would hide the fault in a visual check.
        """
        ticket = self.make()
        lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
        buckets = analytics.analytics(dimension="assignee", now=NOW)["segment"]["buckets"]
        self.assertEqual(buckets, [{"value": str(self.agent.pk), "count": 1}])
        for bucket in buckets:
            self.assertIsInstance(bucket["value"], str)

    def test_an_unknown_dimension_is_no_segment_rather_than_a_crash(self):
        self.make()
        self.assertIsNone(analytics.analytics(dimension="programStage", now=NOW)["segment"])


class WindowTests(AnalyticsTestCase):
    def test_the_window_is_half_open(self):
        """Inclusive of from, exclusive of to, so consecutive months neither
        double-count a ticket nor drop one.
        """
        boundary = datetime(2026, 3, 1, tzinfo=dt_timezone.utc)
        self.make(created=boundary - timedelta(seconds=1))
        self.make(created=boundary)

        february = analytics.analytics(
            start=datetime(2026, 2, 1, tzinfo=dt_timezone.utc), end=boundary, now=NOW
        )
        march = analytics.analytics(
            start=boundary,
            end=datetime(2026, 4, 1, tzinfo=dt_timezone.utc),
            now=NOW,
        )
        self.assertEqual(february["demand"]["volume"], 1)
        self.assertEqual(march["demand"]["volume"], 1)

    def test_the_window_is_reported_back(self):
        start = datetime(2026, 3, 1, tzinfo=dt_timezone.utc)
        result = analytics.analytics(start=start, now=NOW)
        self.assertEqual(result["window"]["from"], start.isoformat())
