"""The data migrations, exercised as ordinary functions.

The suite runs with ``_DisableMigrations`` (config/settings_test.py), so the
migration files themselves are never executed here — the schema is built
straight from the models. A data migration therefore ships completely untested
unless something calls its forward function on purpose, which is what this
module does.

That gap is not theoretical. Commit 07bf433 is a migration that passed
everything and then failed on production Postgres mid-deploy, leaving the
platform half-migrated with login unavailable.

These tests cover what the function *does*. The "will Django run it" half is
covered by `migrate` against a real Postgres database, which
.github/workflows/backend-postgres.yml runs on every push and which this
project's definition of done requires before a release.

Imported through importlib because a module name beginning with a digit is not
a valid identifier, so `from apps.tickets.migrations.0005_... import` will not
parse.
"""
import importlib

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from django.utils import timezone

from apps.tickets.models import (
    Ticket,
    TicketCategory,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
)
from apps.tickets.services import lifecycle
from apps.tickets.services.queue import overdue_condition

User = get_user_model()

retire_programs_groups = importlib.import_module(
    "apps.tickets.migrations.0005_ticket_category_client_list"
).retire_programs_groups

backfill_awaiting = importlib.import_module(
    "apps.tickets.migrations.0007_backfill_awaiting_support_since"
).backfill


class RetireProgramsGroupsTests(TestCase):
    """0005: rows filed under the category the client replaced move to Other."""

    def setUp(self):
        self.requester = User.objects.create_user(
            email="student@example.com", password="pw",
            first_name="Ava", last_name="N",
        )

    def make(self, category):
        ticket = lifecycle.create_ticket(
            user=self.requester,
            category=TicketCategory.ACCOUNT_ACCESS,
            subject="Something",
            body="Please help.",
        )
        # .update() rather than create(category=...): "programs_groups" is no
        # longer a member of the enum, so it can only be put there the way a
        # pre-migration row already holds it — written to the column directly.
        # Django does not enforce choices at the database layer, which is
        # exactly why the rows survive the AlterField and need rewriting.
        Ticket.objects.filter(pk=ticket.pk).update(category=category)
        ticket.refresh_from_db()
        return ticket

    def run_migration(self):
        retire_programs_groups(django_apps, None)

    def test_a_programs_groups_ticket_becomes_other(self):
        ticket = self.make("programs_groups")
        self.run_migration()
        ticket.refresh_from_db()
        self.assertEqual(ticket.category, TicketCategory.OTHER)

    def test_it_does_not_become_general_question(self):
        """Deliberate: "General Question" is a bucket the client reads as
        meaningful on the p52 breakdown, and seeding it with a retired
        category's rows would make that chart lie. "Other" is the honest
        bucket for "we no longer have a name for this"."""
        ticket = self.make("programs_groups")
        self.run_migration()
        ticket.refresh_from_db()
        self.assertNotEqual(ticket.category, TicketCategory.GENERAL_QUESTION)

    def test_tickets_in_other_categories_are_left_alone(self):
        untouched = {}
        for category in (
            TicketCategory.ACCOUNT_ACCESS,
            TicketCategory.CERTIFICATES_RECORDS,
            TicketCategory.FLAGGED_CONTENT,
            TicketCategory.OTHER,
        ):
            untouched[category] = self.make(category)

        self.run_migration()

        for category, ticket in untouched.items():
            with self.subTest(category=category):
                ticket.refresh_from_db()
                self.assertEqual(ticket.category, category)

    def test_a_soft_deleted_ticket_is_rewritten_too(self):
        """A deleted ticket can be restored, and it must not come back
        carrying a category no form can render."""
        ticket = self.make("programs_groups")
        Ticket.objects.filter(pk=ticket.pk).update(
            deleted_at=ticket.created_at
        )
        self.run_migration()
        ticket.refresh_from_db()
        self.assertEqual(ticket.category, TicketCategory.OTHER)

    def test_running_it_twice_changes_nothing_the_second_time(self):
        ticket = self.make("programs_groups")
        self.run_migration()
        ticket.refresh_from_db()
        first = ticket.category
        self.run_migration()
        ticket.refresh_from_db()
        self.assertEqual(ticket.category, first)

    def test_it_leaves_no_row_carrying_a_value_the_model_rejects(self):
        """The point of the whole migration, stated once as an invariant."""
        self.make("programs_groups")
        self.make(TicketCategory.ACCOUNT_ACCESS)
        self.run_migration()
        known = set(TicketCategory.values)
        for ticket in Ticket.objects.all():
            with self.subTest(ticket=ticket.pk):
                self.assertIn(ticket.category, known)


class BackfillAwaitingSupportSinceTests(TestCase):
    """0007: every ticket that predates the column gets its clock.

    Null means "nobody is waiting on support". Without this step the column
    would be null on every existing row, so the whole backlog would read as
    never overdue and the queue's red card would show zero.
    """

    def setUp(self):
        self.requester = User.objects.create_user(
            email="student@example.com", password="pw",
            first_name="Ava", last_name="N",
        )
        self.agent = User.objects.create_user(
            email="agent@example.com", password="pw",
            first_name="Sam", last_name="Reid",
        )

    def make(self, **update):
        ticket = lifecycle.create_ticket(
            user=self.requester,
            category=TicketCategory.ACCOUNT_ACCESS,
            subject="Something",
            body="Please help.",
        )
        if update:
            Ticket.objects.filter(pk=ticket.pk).update(**update)
            ticket.refresh_from_db()
        return ticket

    def clear_column(self):
        """Put the database back the way 0006 leaves it: column present, null
        everywhere. The lifecycle service fills it in as it creates tickets,
        so without this every assertion below would be testing the service
        rather than the migration."""
        Ticket.objects.all().update(awaiting_support_since=None)

    def run_backfill(self):
        self.clear_column()
        backfill_awaiting(django_apps, None)

    def test_a_ticket_nobody_has_answered_starts_from_when_it_was_raised(self):
        """Within a second of created_at, not equal to it.

        The live rule stamps the anchor with its own timezone.now() inside the
        same create() that defaults created_at, so the two are microseconds
        apart and always have been. An assertEqual here would be pinning how
        long an INSERT takes.
        """
        ticket = self.make()
        live = ticket.awaiting_support_since
        self.run_backfill()
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.awaiting_support_since)
        self.assertLess(
            abs((ticket.awaiting_support_since - live).total_seconds()), 1
        )

    def test_an_answered_ticket_comes_back_null(self):
        ticket = self.make()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent, body="Looking now."
        )
        self.run_backfill()
        ticket.refresh_from_db()
        self.assertIsNone(ticket.awaiting_support_since)

    def test_a_ticket_answered_and_then_chased_is_back_on_the_clock(self):
        """The loop the client described. The newest message is the
        requester's, so the ball is with support again."""
        ticket = self.make()
        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent, body="Looking now."
        )
        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="That did not work."
        )
        chase = ticket.messages.filter(
            message_type=TicketMessageType.USER_MESSAGE
        ).latest("created_at")
        self.run_backfill()
        ticket.refresh_from_db()
        self.assertEqual(ticket.awaiting_support_since, chase.created_at)

    def test_a_pending_user_ticket_comes_back_null(self):
        """Not redundant with the timeline rule. An agent can move a ticket to
        "pending user" from the dropdown without writing a reply, so the
        newest message is the requester's and the timeline alone would put it
        on the clock — while the product is telling the requester it is their
        move."""
        ticket = self.make()
        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.PENDING_USER, actor=self.agent
        )
        self.run_backfill()
        ticket.refresh_from_db()
        self.assertIsNone(ticket.awaiting_support_since)

    def test_a_resolved_ticket_comes_back_null(self):
        ticket = self.make()
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        self.run_backfill()
        ticket.refresh_from_db()
        self.assertIsNone(ticket.awaiting_support_since)

    def test_a_ticket_with_no_user_message_falls_back_to_when_it_was_raised(self):
        """A screening ticket has no user message at all — its only row is an
        internal note. Computing purely from the timeline would leave the one
        kind of ticket that most needs chasing permanently invisible."""
        ticket = self.make()
        ticket.messages.filter(
            message_type=TicketMessageType.USER_MESSAGE
        ).delete()
        self.run_backfill()
        ticket.refresh_from_db()
        self.assertEqual(ticket.awaiting_support_since, ticket.created_at)

    def test_the_backfill_makes_an_old_unanswered_ticket_overdue(self):
        """The point of the whole migration, read through the rule that
        consumes it rather than through the column."""
        long_ago = timezone.now() - timedelta_hours(48)
        ticket = self.make(priority=TicketPriority.HIGH, created_at=long_ago)
        ticket.messages.all().update(created_at=long_ago)
        self.run_backfill()
        self.assertIn(
            ticket.pk,
            set(
                Ticket.objects.filter(overdue_condition())
                .values_list("pk", flat=True)
            ),
        )

    def test_a_chased_ticket_anchors_on_the_first_unanswered_message(self):
        """The one the first version got wrong.

        A requester who writes twice with no answer in between has been
        waiting since the FIRST message — that is what the live rule does
        (add_user_reply keeps a running anchor rather than restarting it).
        Anchoring on the newest handed support a fresh window for every chase,
        and on a real ticket the two differed by the whole gap between the
        original message and the chase.
        """
        ticket = self.make()
        live = ticket.awaiting_support_since   # set when it was raised
        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="Anyone there?"
        )
        ticket.refresh_from_db()
        # The chase did not restart it: still the original instant.
        self.assertEqual(ticket.awaiting_support_since, live)

        self.run_backfill()

        ticket.refresh_from_db()
        self.assertLess(
            abs((ticket.awaiting_support_since - live).total_seconds()), 1,
            "the backfill restarted a clock the live rule kept running",
        )

    # Every action an agent or a requester can take that the clock might care
    # about, plus three that must NOT move it. Sequences are generated from
    # this rather than hand-picked: the first version of this test listed
    # eight histories somebody thought of, review found four more that
    # diverged, and "the shapes I thought of" is not a coverage argument.
    CLOCK_ACTIONS = {
        "user_reply": lambda s, t: lifecycle.add_user_reply(
            ticket=t, user=s.requester, body="More from me."
        ),
        "support_reply": lambda s, t: lifecycle.add_support_reply(
            ticket=t, actor=s.agent, body="From support."
        ),
        "reply_and_pend": lambda s, t: lifecycle.add_support_reply(
            ticket=t, actor=s.agent, body="Could you send a screenshot?",
            move_to_pending=True,
        ),
        "mark_pending": lambda s, t: lifecycle.mark_pending(ticket=t, actor=s.agent),
        "drag_to_open": lambda s, t: lifecycle.set_status(
            ticket=t, new_status=TicketStatus.OPEN, actor=s.agent
        ),
        "drag_to_progress": lambda s, t: lifecycle.set_status(
            ticket=t, new_status=TicketStatus.IN_PROGRESS, actor=s.agent
        ),
        "resolve": lambda s, t: lifecycle.resolve(ticket=t, actor=s.agent),
        # None of these three is an answer, so none may move the clock. They
        # are in the generator precisely so that a backfill which quietly
        # treated one of them as an answer would be caught.
        "claim": lambda s, t: lifecycle.claim(ticket=t, actor=s.agent),
        "internal_note": lambda s, t: lifecycle.add_internal_note(
            ticket=t, actor=s.agent, body="Checked the logs."
        ),
    }

    def test_the_backfill_agrees_with_the_live_rule_on_every_history(self):
        """The invariant, over generated histories rather than chosen ones.

        For each sequence of actions: run it through the real service, record
        what the live rule produced, clear the column as migration 0006 leaves
        it, run the backfill, and require the same answer.

        A backfill that merely looks reasonable is not enough. The moment it
        disagrees, the queue right after deployment badges a different set of
        tickets from the one it would have badged had the column always
        existed — and the direction that matters is a ticket the backfill
        leaves null: it can then never go red, whatever happens to it, which
        is the defect the client asked us to remove.
        """
        from itertools import product

        names = list(self.CLOCK_ACTIONS)
        histories = [()] + [(n,) for n in names] + list(product(names, repeat=2))

        built = []
        for history in histories:
            ticket = self.make()
            try:
                for name in history:
                    self.CLOCK_ACTIONS[name](self, ticket)
                    ticket.refresh_from_db()
            except Exception:
                # Some sequences are not reachable (resolving twice, dragging
                # to the status a ticket is already in). Skipping them is
                # right: they are not histories a database can hold.
                continue
            ticket.refresh_from_db()
            built.append((history, ticket, ticket.awaiting_support_since))

        self.assertGreater(len(built), 50, "the generator produced almost nothing")

        def is_overdue(pk):
            return Ticket.objects.filter(overdue_condition(), pk=pk).exists()

        verdicts = {t.pk: is_overdue(t.pk) for _, t, _ in built}

        self.run_backfill()

        diverged = []
        for history, ticket, live in built:
            ticket.refresh_from_db()
            got = ticket.awaiting_support_since
            label = " -> ".join(history) or "(nothing happened)"

            if (got is None) != (live is None):
                diverged.append(f"{label}: live={live!r} backfill={got!r}")
            elif live is not None and abs((got - live).total_seconds()) >= 1:
                diverged.append(
                    f"{label}: {abs((got - live).total_seconds())}s apart"
                )
            elif is_overdue(ticket.pk) != verdicts[ticket.pk]:
                diverged.append(f"{label}: the red badge changed")

        self.assertEqual(
            diverged, [],
            "the backfill and the live rule disagree on "
            f"{len(diverged)} of {len(built)} histories:\n  "
            + "\n  ".join(diverged),
        )

    def test_a_ticket_dragged_back_off_pending_is_still_on_the_clock(self):
        """One generated history, written out because it is the one that broke
        the previous version and the message is worth keeping.

        "Reply and move to pending user", then an agent drags it back to Open.
        The newest message is a support reply, so a backfill that reads only
        messages says nobody is waiting — while the live rule has the clock
        running from the drag-back and the ticket is squarely with support.
        """
        ticket = self.make()
        lifecycle.add_support_reply(
            ticket=ticket, actor=self.agent, body="Screenshot please?",
            move_to_pending=True,
        )
        ticket.refresh_from_db()
        lifecycle.set_status(
            ticket=ticket, new_status=TicketStatus.OPEN, actor=self.agent
        )
        ticket.refresh_from_db()
        live = ticket.awaiting_support_since
        self.assertIsNotNone(live)

        self.run_backfill()

        ticket.refresh_from_db()
        self.assertIsNotNone(
            ticket.awaiting_support_since,
            "a ticket dragged back off pending user is with support again and "
            "must be able to go overdue",
        )
        self.assertLess(
            abs((ticket.awaiting_support_since - live).total_seconds()), 1
        )

    def test_two_events_at_the_very_same_instant_resolve_the_way_the_service_does(self):
        """Equal timestamps, which generated histories never produce.

        Real calls are microseconds apart, so ordering is decided for us and a
        tie-break is never exercised. Seeded data and any future bulk import
        can land two rows on the same instant, and "arm then disarm" is not
        the same as "disarm then arm" — one leaves the ticket on the clock
        forever, the other takes it off.

        The service's answer for this pair is unambiguous:
        add_support_reply(move_to_pending=True) writes a reply and a status
        change together and BOTH stop the clock, so a tie must stop it.
        """
        from apps.audit.models import AuditLog

        ticket = self.make()
        lifecycle.add_user_reply(
            ticket=ticket, user=self.requester, body="Still stuck."
        )
        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Fixed.")

        # Force the requester's message and the support reply onto one instant.
        instant = timezone.now()
        ticket.messages.filter(
            message_type__in=[
                TicketMessageType.USER_MESSAGE,
                TicketMessageType.SUPPORT_REPLY,
            ]
        ).update(created_at=instant)
        AuditLog.objects.filter(
            entity_type="ticket", entity_id=ticket.pk
        ).update(created_at=instant)

        self.run_backfill()

        ticket.refresh_from_db()
        self.assertIsNone(
            ticket.awaiting_support_since,
            "a reply and a message at the same instant must leave the clock "
            "stopped, the way add_support_reply(move_to_pending=True) does",
        )

    def test_a_missing_audit_row_cannot_leave_a_closed_ticket_on_the_clock(self):
        """What the status guard at the end of the replay is actually for.

        Every reachable history replays correctly without it, which is why a
        mutation that removes it survives an ordinary suite — the guard is
        redundant defence, and redundant defence only shows its worth in the
        case it was written for. That case is an audit log with a hole in it:
        rows purged by a retention policy, or a ticket whose state changed
        before this project started auditing.

        Without the guard such a ticket ends up on the queue's red card while
        sitting in a state the product calls closed.
        """
        from apps.audit.models import AuditLog

        ticket = self.make()
        lifecycle.resolve(ticket=ticket, actor=self.agent)
        # The hole: the resolve happened, its audit row did not survive.
        AuditLog.objects.filter(
            entity_type="ticket", entity_id=ticket.pk, action="resolve"
        ).delete()

        self.run_backfill()

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)
        self.assertIsNone(
            ticket.awaiting_support_since,
            "the current status is authoritative: a resolved ticket is not "
            "waiting on support, whatever the recovered history says",
        )

    def test_a_deleted_support_reply_does_not_stop_the_clock(self):
        """Soft-deleted messages are excluded, and that has to stay true.

        Nothing writes TicketMessage.deleted_at today — it is only ever
        filtered on — so this guards a column that is dormant rather than one
        that is exercised. It is here because the day message deletion is
        built, a backfill that counted deleted replies as answers would take
        tickets off the clock on the strength of a reply nobody can read.
        """
        ticket = self.make()
        lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Gone.")
        ticket.messages.filter(
            message_type=TicketMessageType.SUPPORT_REPLY
        ).update(deleted_at=timezone.now())

        self.run_backfill()

        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.awaiting_support_since)

    def test_running_it_twice_is_the_same_as_running_it_once(self):
        ticket = self.make()
        self.run_backfill()
        ticket.refresh_from_db()
        once = ticket.awaiting_support_since
        backfill_awaiting(django_apps, None)
        ticket.refresh_from_db()
        self.assertEqual(ticket.awaiting_support_since, once)


def timedelta_hours(n):
    from datetime import timedelta

    return timedelta(hours=n)
