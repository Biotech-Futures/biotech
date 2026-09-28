"""The queue's filters, at the level the service defines them.

The HTTP tests cover the same ground through the view; these sit under it,
because the invariant the Unassigned bucket has to hold is between two
functions in this module rather than between a request and a response.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.tickets.models import SupportScope, TicketCategory, TicketStatus
from apps.tickets.services import lifecycle, queue

User = get_user_model()


class UnassignedFilterTests(TestCase):
    """"Unassigned" carries a hidden "and not resolved", and exactly two
    filters take it off.

    The sentinel exists so the Unassigned card can be clicked through, and
    that card counts unowned tickets that are not resolved. Applied to every
    request that used the value, the exclusion made the queue deny tickets an
    agent could name: choosing Resolved beside it emptied the table, and
    searching an unowned resolved ticket by its own number answered "No
    tickets match these filters".

    Status and search are the two, because those are the two ways an agent
    names a resolved ticket. Region, category and priority only narrow the
    pile, and the card link carries whichever of them is already on screen.
    Letting them lift the exclusion puts a resolved row back on the card's own
    path, which is the mismatch the exclusion is here to prevent.
    """

    def setUp(self):
        self.requester = User.objects.create_user(
            email="rowan@example.com", password="pass1234",
            first_name="Rowan", last_name="Ellis",
        )
        self.agent = User.objects.create_user(
            email="queue-agent@example.com", password="pass1234",
            first_name="Sana", last_name="Reid",
        )
        SupportScope.objects.create(user=self.agent)
        self.owned = self.make_ticket("Someone is on this")
        lifecycle.claim(ticket=self.owned, actor=self.agent)
        self.waiting = self.make_ticket("Nobody has this")
        # Unowned and resolved: the row the two definitions disagree about.
        self.settled = self.make_ticket("Nobody has this, and it is done")
        lifecycle.resolve(ticket=self.settled, actor=self.agent)

    def make_ticket(self, subject):
        return lifecycle.create_ticket(
            user=self.requester,
            category=TicketCategory.ACCOUNT_ACCESS,
            subject=subject,
            body="I cannot sign in.",
        )

    def ids_for(self, **filters):
        return set(
            queue.apply_filters(queue.live_tickets(), **filters)
            .values_list("pk", flat=True)
        )

    def test_the_bucket_on_its_own_is_live_work_only(self):
        """What the card promises when it is the only thing selected."""
        self.assertEqual(
            self.ids_for(assignee=queue.UNASSIGNED), {self.waiting.pk}
        )

    def test_the_card_and_the_filter_it_links_to_agree(self):
        """Computed separately, so this is what keeps them equal.

        setUp seeds an unowned resolved ticket precisely so this comparison
        has something to catch.
        """
        self.assertEqual(
            queue.summary()["unassigned"],
            len(self.ids_for(assignee=queue.UNASSIGNED)),
        )

    def test_asking_for_resolved_and_unowned_finds_it(self):
        self.assertEqual(
            self.ids_for(
                assignee=queue.UNASSIGNED, status=TicketStatus.RESOLVED
            ),
            {self.settled.pk},
        )

    def test_searching_an_unowned_resolved_ticket_by_number_finds_it(self):
        """The commoner route in, because the card sets this filter itself.

        An agent who arrives from the Unassigned card and searches a ticket
        number is not asking about the card's number any more.
        """
        self.assertEqual(
            self.ids_for(
                assignee=queue.UNASSIGNED, search=self.settled.ticket_number
            ),
            {self.settled.pk},
        )

    def test_a_narrower_question_does_not_widen_the_owner_half(self):
        """Only the status half of the sentinel gives way.

        A ticket somebody owns must not appear under "Unassigned" whatever
        else is selected.
        """
        self.assertEqual(
            self.ids_for(
                assignee=queue.UNASSIGNED, status=TicketStatus.IN_PROGRESS
            ),
            set(),
        )

    def test_a_region_beside_the_bucket_does_not_let_resolved_back_in(self):
        """The card link carries the region already selected, so this is the
        card's own path, not a corner of it."""
        self.assertEqual(
            self.ids_for(
                assignee=queue.UNASSIGNED, region=queue.UNKNOWN_REGION
            ),
            {self.waiting.pk},
        )

    def test_a_category_beside_the_bucket_does_not_let_resolved_back_in(self):
        self.assertEqual(
            self.ids_for(
                assignee=queue.UNASSIGNED, category=TicketCategory.ACCOUNT_ACCESS
            ),
            {self.waiting.pk},
        )

    def test_a_priority_beside_the_bucket_does_not_let_resolved_back_in(self):
        self.assertEqual(
            self.ids_for(
                assignee=queue.UNASSIGNED, priority=self.settled.priority
            ),
            {self.waiting.pk},
        )

    def test_the_card_still_agrees_once_the_pile_is_narrowed(self):
        """Same comparison as above, made along the link the card builds.

        The three filters below are the ones a card click carries with it, so
        each is checked against the card rather than against itself.
        """
        for extra in (
            {"region": queue.UNKNOWN_REGION},
            {"category": TicketCategory.ACCOUNT_ACCESS},
            {"priority": self.settled.priority},
        ):
            with self.subTest(**extra):
                self.assertLessEqual(
                    len(self.ids_for(assignee=queue.UNASSIGNED, **extra)),
                    queue.summary()["unassigned"],
                )
