import threading
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

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
