"""seed_e2e: the accounts the Playwright suite (frontend/e2e/tickets.spec.ts)
signs in with.

The agent has to be the account the People page makes for a support agent:
queue access AND the role "support". The portal decides who an account is
from the role (stores/auth.ts), so an agent with queue access and no role
signed in to the student dashboard, and the end-to-end suite was testing an
account the product never creates.
"""

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from io import StringIO

from apps.resources.models import RoleAssignmentHistory, Roles
from apps.tickets.management.commands.seed_e2e import (
    AGENT_EMAIL,
    AGENT_PASSWORD,
    STUDENT_EMAIL,
)
from apps.tickets.models import SupportScope
from apps.users.models import User
from apps.users.models.admin_scope import AdminScope


def seed():
    # --force: the test database is ":memory:", which carries none of the
    # scratch-name markers the command looks for. DEBUG: the test runner
    # switches it off, and the command refuses to run without it.
    with override_settings(DEBUG=True):
        call_command("seed_e2e", "--force", stdout=StringIO())


def open_assignments(user):
    now = timezone.now()
    return RoleAssignmentHistory.objects.filter(user=user, valid_from__lte=now).filter(
        valid_to__isnull=True
    )


class SeedE2EAgentRoleTests(TestCase):
    def me_as_agent(self):
        self.assertTrue(self.client.login(email=AGENT_EMAIL, password=AGENT_PASSWORD))
        response = self.client.get("/api/v1/users/me/")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_the_agent_is_a_pure_support_agent_as_the_portal_reads_it(self):
        seed()
        me = self.me_as_agent()
        # The three things the portal's isSupportOnly and canWorkTickets
        # getters read.
        self.assertEqual(me["current_role_name"], "support")
        self.assertIs(me["isSupport"], True)
        self.assertIs(me["isAdmin"], False)
        # And is_staff, which the portal reads as "admin" before it looks at
        # the role, whenever a response carries it.
        agent = User.objects.get(email=AGENT_EMAIL)
        self.assertFalse(agent.is_staff)
        self.assertFalse(agent.is_superuser)

    def test_rerunning_writes_no_second_role_row_or_assignment(self):
        seed()
        seed()
        agent = User.objects.get(email=AGENT_EMAIL)
        self.assertEqual(Roles.objects.filter(role_name__iexact="support").count(), 1)
        self.assertEqual(open_assignments(agent).count(), 1)
        self.assertEqual(RoleAssignmentHistory.objects.filter(user=agent).count(), 1)
        self.assertEqual(SupportScope.objects.filter(user=agent).count(), 1)

    def test_an_existing_support_row_is_reused_whatever_its_case(self):
        # resolve_role_id is a case-insensitive get_or_create, the admin user
        # service's own lookup. A second, lower-case row next to "Support" is
        # the duplicate the demo database already suffers from.
        existing = Roles.objects.create(role_name="Support")
        seed()
        agent = User.objects.get(email=AGENT_EMAIL)
        self.assertEqual(Roles.objects.filter(role_name__iexact="support").count(), 1)
        self.assertEqual(open_assignments(agent).get().role_id, existing.id)

    def test_a_drifted_agent_is_moved_back_to_support_with_history_kept(self):
        # Someone changed the account by hand: another role, and an admin
        # marker on top. The rerun heals both, the way the People page would
        # move a role (close the old assignment, open a new one).
        student_role = Roles.objects.create(role_name="student")
        agent = User.objects.create_user(
            email=AGENT_EMAIL, password="whatever", is_staff=True, is_superuser=True
        )
        earlier = timezone.now() - timedelta(days=3)
        RoleAssignmentHistory.objects.create(
            user=agent, role=student_role, valid_from=earlier, valid_to=None
        )
        AdminScope.objects.create(user=agent)

        seed()

        current = open_assignments(agent).select_related("role").get()
        self.assertEqual(current.role.role_name, "support")
        old = RoleAssignmentHistory.objects.get(user=agent, role=student_role)
        self.assertIsNotNone(old.valid_to)
        self.assertFalse(AdminScope.objects.filter(user=agent).exists())
        agent.refresh_from_db()
        self.assertFalse(agent.is_staff)
        self.assertFalse(agent.is_superuser)
        me = self.me_as_agent()
        self.assertEqual(me["current_role_name"], "support")
        self.assertIs(me["isAdmin"], False)

    def test_the_student_is_left_without_support_access_or_role(self):
        seed()
        student = User.objects.get(email=STUDENT_EMAIL)
        self.assertFalse(SupportScope.objects.filter(user=student).exists())
        self.assertFalse(RoleAssignmentHistory.objects.filter(user=student).exists())
