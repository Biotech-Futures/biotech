from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.common.rbac import (
    active_role_ids,
    active_role_names,
    get_active_role_name,
    group_participant_qs,
    is_admin,
    user_has_role,
)
from apps.common.role_names import (
    ROLE_ADMIN,
    ROLE_MENTOR,
    ROLE_STUDENT,
    get_role_by_name,
    try_get_role_by_name,
)
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import AdminScope


User = get_user_model()


class CommonRBACTests(TestCase):
    def setUp(self):
        self.group = Groups.objects.create(group_name="Primary Group")

        # Two admins that in the old model were a "global admin" and a
        # "track admin" respectively. Under the single-tier model an
        # AdminScope row is the only thing that matters, so both are now
        # simply admins.
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password="pw",
            first_name="Some",
            last_name="Admin",
        )
        self.second_admin = User.objects.create_user(
            email="second-admin@test.com",
            password="pw",
            first_name="Second",
            last_name="Admin",
        )
        self.mentor = User.objects.create_user(
            email="mentor@test.com",
            password="pw",
            first_name="Mentor",
            last_name="User",
        )

        self.admin_role = Roles.objects.create(role_name="admin")
        self.mentor_role = Roles.objects.create(role_name="mentor")
        now = timezone.now()
        future = now + timedelta(days=365)

        AdminScope.objects.create(user=self.admin_user)
        AdminScope.objects.create(user=self.second_admin)
        RoleAssignmentHistory.objects.create(user=self.mentor, role=self.mentor_role, valid_from=now, valid_to=future)
        GroupMembership.objects.create(user=self.mentor, group=self.group, membership_role="mentor")

    def test_is_admin_accepts_any_admin_scope_row(self):
        # Both formerly-distinct admin tiers collapse to a single check:
        # any AdminScope row means admin.
        self.assertTrue(is_admin(self.admin_user))
        self.assertTrue(is_admin(self.second_admin))
        self.assertFalse(is_admin(self.mentor))

    def test_active_role_helpers_resolve_current_role_assignments(self):
        self.assertEqual(active_role_names(self.mentor), {"mentor"})
        self.assertEqual(active_role_ids(self.mentor), {self.mentor_role.id})

    def test_group_participant_qs_only_returns_active_memberships(self):
        self.assertTrue(group_participant_qs(self.mentor, self.group.id).exists())
        membership = GroupMembership.objects.get(user=self.mentor, group=self.group, left_at__isnull=True)
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])

        self.assertFalse(group_participant_qs(self.mentor, self.group.id).exists())

    def test_is_admin_ignores_is_staff_and_is_superuser(self):
        staff_user = User.objects.create_user(email="staff@test.com", password="pw", is_staff=True)
        super_user = User.objects.create_user(email="super@test.com", password="pw", is_superuser=True)
        self.assertFalse(is_admin(staff_user))
        self.assertFalse(is_admin(super_user))

    def test_is_admin_requires_an_admin_scope_row(self):
        staff_user = User.objects.create_user(email="ops-staff@test.com", password="pw", is_staff=True)
        scoped_user = User.objects.create_user(email="ops-scoped@test.com", password="pw")
        AdminScope.objects.create(user=scoped_user)

        # is_staff alone never confers admin; only an AdminScope row does.
        self.assertFalse(is_admin(staff_user))
        self.assertTrue(is_admin(scoped_user))

    def test_is_admin_ignores_role_assignments(self):
        admin_role = get_role_by_name(ROLE_ADMIN)
        user = User.objects.create_user(email="role-admin@test.com", password="pw")
        now = timezone.now()
        RoleAssignmentHistory.objects.create(
            user=user, role=admin_role, valid_from=now, valid_to=now + timedelta(days=365)
        )
        # An "admin" role assignment is not the same as an AdminScope row.
        self.assertFalse(is_admin(user))

    def test_get_active_role_name_returns_normalized_role(self):
        self.assertEqual(get_active_role_name(self.mentor), ROLE_MENTOR)

    def test_get_active_role_name_handles_anonymous_and_no_role(self):
        no_role_user = User.objects.create_user(email="noroles@test.com", password="pw")
        self.assertIsNone(get_active_role_name(no_role_user))
        self.assertIsNone(get_active_role_name(None))

    def test_user_has_role_matches_active_roles_case_insensitively(self):
        self.assertTrue(user_has_role(self.mentor, "MENTOR"))
        self.assertFalse(user_has_role(self.mentor, ROLE_STUDENT))
        self.assertFalse(user_has_role(self.mentor))

    def test_role_name_lookup_is_case_insensitive_and_pk_independent(self):
        # Force a different PK ordering than the names imply to prove we
        # do not rely on numeric IDs.
        Roles.objects.create(role_name="filler-role-1")
        Roles.objects.create(role_name="filler-role-2")
        student = Roles.objects.create(role_name="Student")

        self.assertEqual(get_role_by_name("student"), student)
        self.assertEqual(get_role_by_name("STUDENT"), student)
        self.assertIsNone(try_get_role_by_name("does-not-exist"))
