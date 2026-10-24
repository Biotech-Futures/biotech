from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from apps.tickets.models import SupportScope
from apps.tickets.permissions import IsSupportScoped, is_support
from apps.users.models import AdminScope

User = get_user_model()


class IsSupportTests(TestCase):
    """The four quadrants of DEC-001.

    Every admin can work the queue; not every agent is an admin. Both halves
    of that OR are load-bearing, so both are pinned here.
    """

    def setUp(self):
        self.nobody = User.objects.create_user(email="student@example.com", password="pass1234")
        self.agent = User.objects.create_user(email="agent@example.com", password="pass1234")
        self.admin = User.objects.create_user(email="admin@example.com", password="pass1234")
        self.both = User.objects.create_user(email="both@example.com", password="pass1234")

        SupportScope.objects.create(user=self.agent)
        AdminScope.objects.create(user=self.admin)
        SupportScope.objects.create(user=self.both)
        AdminScope.objects.create(user=self.both)

    def test_an_agent_with_only_a_support_row_is_support(self):
        self.assertTrue(is_support(self.agent))

    def test_an_admin_is_support_without_a_support_row(self):
        self.assertTrue(is_support(self.admin))

    def test_holding_both_rows_is_support(self):
        self.assertTrue(is_support(self.both))

    def test_an_ordinary_user_is_not_support(self):
        self.assertFalse(is_support(self.nobody))

    def test_an_anonymous_visitor_is_not_support_and_does_not_blow_up(self):
        # DEC-019 B3: querying with AnonymousUser raises TypeError, which would
        # reach the client as a 500 instead of a 403.
        self.assertFalse(is_support(AnonymousUser()))

    def test_a_missing_user_is_not_support(self):
        self.assertFalse(is_support(None))


class IsSupportScopedTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsSupportScoped()
        self.agent = User.objects.create_user(email="agent2@example.com", password="pass1234")
        SupportScope.objects.create(user=self.agent)
        self.outsider = User.objects.create_user(email="outsider@example.com", password="pass1234")

    def _check(self, user):
        request = self.factory.get("/api/v1/admin/tickets/")
        request.user = user
        return self.permission.has_permission(request, view=None)

    def test_support_passes(self):
        self.assertTrue(self._check(self.agent))

    def test_a_signed_in_outsider_is_refused(self):
        self.assertFalse(self._check(self.outsider))

    def test_an_anonymous_visitor_is_refused(self):
        self.assertFalse(self._check(AnonymousUser()))


class BeingSignedInIsTheOnlyRequirementTests(TestCase):
    """Who may raise a ticket, pinned on purpose.

    Asked on 2026-09-04 whether "people need to be signed in to BIOTech
    Connect to raise a ticket, but they do not need to be registered in any
    programme" was right, the client answered "Correct".

    That is what the code already did, but only by accident: nothing said so,
    so anyone adding a sensible-looking guard — members of a group, students
    with a supervisor, people whose registration is complete — would have been
    tightening a rule the client has settled, and every existing test would
    still have passed. These tests make that a decision somebody has to
    deliberately overturn.
    """

    def setUp(self):
        # Deliberately bare. No group, no role assignment, no profile, no
        # workshop, no supervisor, no guardian consent: an account that exists
        # and nothing more.
        self.stranger = User.objects.create_user(
            email="stranger@example.com", password="pass1234",
            first_name="Kim", last_name="Vo",
        )

    def test_an_account_in_no_programme_can_raise_a_ticket(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.stranger)
        response = client.post("/api/v1/tickets/", {
            "category": "account_access",
            "subject": "I cannot get in",
            "body": "My login code never arrives.",
        })
        self.assertEqual(response.status_code, 201, response.data)

    def test_they_can_read_and_reply_to_their_own_ticket(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.stranger)
        created = client.post("/api/v1/tickets/", {
            "category": "account_access",
            "subject": "I cannot get in",
            "body": "My login code never arrives.",
        }).data["data"]

        self.assertEqual(
            client.get(f"/api/v1/tickets/{created['id']}/").status_code, 200
        )
        self.assertEqual(
            client.post(
                f"/api/v1/tickets/{created['id']}/messages/",
                {"body": "Still nothing."},
            ).status_code,
            201,
        )

    def test_signing_out_is_the_only_thing_that_stops_them(self):
        """403, not "401 or 403".

        This accepted either code, so no mutation of the permission layer
        could make it fail. The looser assertion also carried the same wrong
        belief the permission docstring did: DRF only answers 401 when an
        authentication class offers a WWW-Authenticate header, and the one
        this project configures does not. There is no deployment of this
        codebase in which the 401 branch is reachable.
        """
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.post("/api/v1/tickets/", {
            "category": "account_access",
            "subject": "x",
            "body": "y",
        })

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("WWW-Authenticate", response.headers)

    def test_no_requester_facing_ticket_view_consults_a_role_or_a_group(self):
        """Read as source, because a permission that is never exercised by a
        test is a permission that can be added without any test noticing.

        Narrow on purpose: it looks for the platform's own membership and
        enrolment gates by name. It is not a general ban on the word "role" —
        `requester_role` is a snapshot the ticket writes about the person, not
        a check on them.
        """
        import re
        from pathlib import Path

        from django.conf import settings

        source = (
            Path(settings.BASE_DIR) / "apps" / "tickets" / "views.py"
        ).read_text()
        # Comments describe the rule; only code can enforce it.
        code = "\n".join(
            line for line in source.splitlines()
            if not line.lstrip().startswith("#")
        )
        for gate in (
            "GroupMembership",
            "RoleAssignmentHistory",
            "has_join_permission",
            "StudentProfile",
            "Workshop",
            "IsGroupMember",
        ):
            with self.subTest(gate=gate):
                self.assertNotIn(
                    gate, code,
                    f"{gate} appears in the requester-facing ticket views. "
                    "The client settled on 2026-09-04 that raising a ticket "
                    "needs a sign-in and nothing else; adding an enrolment "
                    "check is a decision to take with them, not a tidy-up.",
                )
        self.assertTrue(re.search(r"permission_classes\s*=\s*\[IsAuthenticated\]", code))

