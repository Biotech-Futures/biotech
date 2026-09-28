"""Snapshot paging, at the level the service defines it.

Specifically the one clause with two different right answers: what happens to
a ticket that is deleted part way through a walk. The module says it stays in
the set, and that is true of the requester's own list and false of the support
queue, because deleting a ticket moves the column the queue is ordered by and
does not move the one the requester's list is ordered by. Both answers came
out of the same line with nothing pinning either.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.tickets.models import SupportScope, Ticket, TicketCategory
from apps.tickets.services import lifecycle
from apps.tickets.services.paging import after_cursor, as_at

User = get_user_model()


class DeletedMidWalkTests(TestCase):
    PAGE = 2

    def setUp(self):
        self.requester = User.objects.create_user(
            email="ines@example.com", password="pass1234",
            first_name="Ines", last_name="Faber",
        )
        self.admin = User.objects.create_user(
            email="paging-admin@example.com", password="pass1234",
            first_name="Dana", last_name="Okafor",
        )
        SupportScope.objects.create(user=self.admin)
        # Six, so a two-row page one leaves the deleted row on page two with
        # rows behind it. Newest first, so the last raised is served first.
        self.tickets = [self.make_ticket(f"Enquiry {i}") for i in range(6)]

    def make_ticket(self, subject):
        return lifecycle.create_ticket(
            user=self.requester,
            category=TicketCategory.ACCOUNT_ACCESS,
            subject=subject,
            body="I cannot sign in.",
        )

    def walk(self, queryset, as_of, *, activity_field):
        """Page one, then page two off page one's cursor. Ids only."""
        ordered = as_at(queryset, as_of, activity_field=activity_field)
        first = list(ordered[: self.PAGE])
        last = first[-1]
        cursor = (getattr(last, activity_field), last.pk)
        second = list(
            after_cursor(ordered, cursor, activity_field=activity_field)[: self.PAGE]
        )
        return [t.pk for t in first], [t.pk for t in second]

    def mine(self):
        return Ticket.objects.filter(created_by=self.requester)

    def test_a_ticket_deleted_mid_walk_stays_in_the_requesters_own_walk(self):
        """Their list is ordered by ``updated_at``, which a delete leaves alone.

        The row is held in by the ``deleted_at`` clause and by nothing else,
        so the reader keeps their place and the detail view is what tells them
        the ticket has gone.
        """
        as_of = timezone.now()
        doomed = self.tickets[3]

        first, _ = self.walk(self.mine(), as_of, activity_field="updated_at")
        lifecycle.soft_delete(ticket=doomed, actor=self.admin)
        _, second = self.walk(self.mine(), as_of, activity_field="updated_at")

        self.assertNotIn(doomed.pk, first)
        self.assertIn(doomed.pk, second)

    def test_a_ticket_deleted_mid_walk_leaves_the_support_queues_walk(self):
        """The queue is ordered by ``support_updated_at``, which a delete moves.

        So the row goes out through the activity filter before the
        ``deleted_at`` clause is ever reached, and the rows behind it keep
        their order.
        """
        as_of = timezone.now()
        doomed = self.tickets[3]

        first, _ = self.walk(
            Ticket.objects.all(), as_of, activity_field="support_updated_at"
        )
        lifecycle.soft_delete(ticket=doomed, actor=self.admin)
        _, second = self.walk(
            Ticket.objects.all(), as_of, activity_field="support_updated_at"
        )

        self.assertNotIn(doomed.pk, first + second)
        self.assertEqual(
            second, [self.tickets[2].pk, self.tickets[1].pk],
            "the rows behind the deleted one shifted",
        )

    def test_a_ticket_deleted_before_the_snapshot_is_not_in_the_walk_at_all(self):
        """Membership is decided at the snapshot, in both directions."""
        lifecycle.soft_delete(ticket=self.tickets[3], actor=self.admin)
        as_of = timezone.now()

        served = list(
            as_at(self.mine(), as_of, activity_field="updated_at")
            .values_list("pk", flat=True)
        )

        self.assertNotIn(self.tickets[3].pk, served)
        self.assertEqual(len(served), 5)
