import threading
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from apps.tickets.models import Ticket, TicketCategory, TicketCounter
from apps.tickets.services.numbering import allocate_ticket_number


def make_ticket(number, **overrides):
    payload = {
        "ticket_number": number,
        "subject": "Login issue",
        "body": "I cannot sign in.",
        "category": TicketCategory.ACCOUNT_ACCESS,
    }
    payload.update(overrides)
    return Ticket.objects.create(**payload)


class TicketNumberFormatTests(TestCase):
    def test_the_first_number_of_a_year_is_five_padded_digits(self):
        with patch("apps.tickets.services.numbering.timezone.now") as now:
            now.return_value = datetime(2026, 3, 1, 12, 0, tzinfo=dt_timezone.utc)
            self.assertEqual(allocate_ticket_number(), "SUP-2026-00001")

    def test_numbers_run_consecutively(self):
        with patch("apps.tickets.services.numbering.timezone.now") as now:
            now.return_value = datetime(2026, 3, 1, 12, 0, tzinfo=dt_timezone.utc)
            issued = [allocate_ticket_number() for _ in range(3)]
        self.assertEqual(
            issued,
            ["SUP-2026-00001", "SUP-2026-00002", "SUP-2026-00003"],
        )

    def test_the_counter_restarts_at_one_in_the_new_year(self):
        # DEC-019 B1: the year is read in UTC, so the boundary is the UTC one.
        with patch("apps.tickets.services.numbering.timezone.now") as now:
            now.return_value = datetime(2026, 12, 31, 23, 59, tzinfo=dt_timezone.utc)
            last_of_2026 = allocate_ticket_number()
            now.return_value = datetime(2027, 1, 1, 0, 1, tzinfo=dt_timezone.utc)
            first_of_2027 = allocate_ticket_number()

        self.assertEqual(last_of_2026, "SUP-2026-00001")
        self.assertEqual(first_of_2027, "SUP-2027-00001")
        self.assertEqual(
            sorted(TicketCounter.objects.values_list("year", "last_number")),
            [(2026, 1), (2027, 1)],
        )


class TicketNumberRollbackTests(TestCase):
    """A submission that fails after taking a number must give it back.

    Numbers are what the requester quotes back to us, so a gap in the sequence
    is not cosmetic: it looks like a ticket that was deleted.
    """

    def test_a_failed_submission_does_not_burn_a_number(self):
        with patch("apps.tickets.services.numbering.timezone.now") as now:
            now.return_value = datetime(2026, 5, 1, 9, 0, tzinfo=dt_timezone.utc)
            first = allocate_ticket_number()
            make_ticket(first)

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    doomed = allocate_ticket_number()
                    self.assertEqual(doomed, "SUP-2026-00002")
                    # Force the insert to fail the way a real collision would.
                    make_ticket(first, subject="Collides with an issued number")

            self.assertEqual(TicketCounter.objects.get(year=2026).last_number, 1)
            # The number the failed attempt held is handed out again, unburnt.
            self.assertEqual(allocate_ticket_number(), "SUP-2026-00002")


@skipUnlessDBFeature("has_select_for_update")
class TicketNumberRowLockTests(TransactionTestCase):
    """The row lock is the thing that makes concurrent submissions safe.

    Skipped on SQLite: Django drops ``FOR UPDATE`` there silently, so this
    would pass without testing anything. It runs against local Postgres.
    """

    def test_two_concurrent_allocations_never_take_the_same_number(self):
        issued = []
        failures = []
        start = threading.Barrier(2, timeout=10)

        def worker():
            try:
                start.wait()
                issued.append(allocate_ticket_number())
            except Exception as exc:  # surfaced below so the assert explains itself
                failures.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        self.assertEqual(failures, [])
        self.assertEqual(len(issued), 2)
        self.assertEqual(len(set(issued)), 2, f"the same number went out twice: {issued}")
        self.assertEqual(TicketCounter.objects.get(year=int(issued[0][4:8])).last_number, 2)

    def test_the_lock_holds_when_the_counter_row_already_exists(self):
        """The case the test above cannot reach.

        With an empty table both threads take ``get_or_create``'s INSERT
        branch, and what serialises them is the unique index on ``year``, not
        ``FOR UPDATE`` — remove the lock and that test still passes. Every
        allocation after the first ticket of the year takes the other branch:
        SELECT the row, add one, write it back. That read-then-write gap is
        what the lock exists for, so seed the row and make both threads race
        through it.
        """
        year = timezone.now().year
        TicketCounter.objects.create(year=year, last_number=41)

        issued = []
        failures = []
        start = threading.Barrier(2, timeout=10)

        def worker():
            try:
                start.wait()
                issued.append(allocate_ticket_number())
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
        self.assertEqual(
            sorted(issued),
            [f"SUP-{year}-00042", f"SUP-{year}-00043"],
            f"both threads read the same counter value: {issued}",
        )
        self.assertEqual(TicketCounter.objects.get(year=year).last_number, 43)


class TicketNumberCatchUpTests(TestCase):
    """A counter that has fallen behind the numbers already in the table.

    Nothing inside the app can put it there. A partial restore or a row
    inserted by hand can, and until this the platform did not come back from
    it: the number returned on the failed insert, so the next submission took
    the same one and failed the same way, and so did every submission after it
    for the rest of the year.
    """

    def setUp(self):
        self.clock = patch("apps.tickets.services.numbering.timezone.now")
        now = self.clock.start()
        now.return_value = datetime(2026, 7, 1, 9, 0, tzinfo=dt_timezone.utc)
        self.addCleanup(self.clock.stop)

    def test_a_block_of_restored_numbers_is_stepped_over_in_one_go(self):
        for number in range(2, 7):
            make_ticket(f"SUP-2026-{number:05d}")
        TicketCounter.objects.create(year=2026, last_number=1)

        self.assertEqual(allocate_ticket_number(), "SUP-2026-00007")
        self.assertEqual(TicketCounter.objects.get(year=2026).last_number, 7)

    def test_free_numbers_below_the_block_are_still_handed_out(self):
        """The counter only jumps when it lands on something.

        A gap under the restored block is a number nobody is using, and using
        it keeps the sequence without a hole in it, which is the whole reason
        a failed submission gives its number back.
        """
        make_ticket("SUP-2026-00005")
        TicketCounter.objects.create(year=2026, last_number=1)

        self.assertEqual(
            [allocate_ticket_number() for _ in range(4)],
            [
                "SUP-2026-00002",
                "SUP-2026-00003",
                "SUP-2026-00004",
                "SUP-2026-00006",
            ],
        )

    def test_a_soft_deleted_ticket_still_holds_its_number(self):
        """Deleting the ticket in the way is not a way out of this.

        The row stays in the table, and so does its hold on the unique
        constraint, so a number handed out again would fail the insert exactly
        as before.
        """
        make_ticket("SUP-2026-00002", deleted_at=timezone.now())
        TicketCounter.objects.create(year=2026, last_number=1)

        self.assertEqual(allocate_ticket_number(), "SUP-2026-00003")

    def test_submissions_keep_working_after_the_counter_falls_behind(self):
        """The consequence, rather than the mechanism.

        Three submissions in a row against a counter pointing into a restored
        block. Before the step-over every one of them was an IntegrityError
        and the queue took no tickets at all.
        """
        make_ticket("SUP-2026-00002")
        make_ticket("SUP-2026-00003")
        TicketCounter.objects.create(year=2026, last_number=1)

        issued = []
        for _ in range(3):
            number = allocate_ticket_number()
            make_ticket(number)
            issued.append(number)

        self.assertEqual(
            issued, ["SUP-2026-00004", "SUP-2026-00005", "SUP-2026-00006"]
        )

    def test_a_number_nobody_can_parse_does_not_wind_the_counter_back(self):
        """The premise here is a table somebody edited by hand, and a number
        edited by hand is the one most likely not to be five digits.

        Fixed-width padding is what makes the string order the numeric order,
        so anything that is not a digit sorts above every real number and is
        the one the step-over reads. It cannot be turned into a number, so it
        counts as nothing. "The highest in use is nothing" must not become
        "start again from one", which would hand out numbers below the ones
        already issued for the rest of the year.
        """
        make_ticket("SUP-2026-00005")
        make_ticket("SUP-2026-XXXXX")
        TicketCounter.objects.create(year=2026, last_number=4)

        allocate_ticket_number()

        self.assertGreaterEqual(
            TicketCounter.objects.get(year=2026).last_number, 5
        )
