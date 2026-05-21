"""Regression tests for ``apps.common.role_names``.

These tests pin the contract that:

* The four ``ROLE_*`` constants match the canonical lowercase strings
  used in the DB seed (``create_test_users.py`` / data migrations) and
  in ``apps.common.rbac.active_role_names``.
* ``get_role_by_name`` returns the right ``Roles`` row, is case-insensitive,
  and raises ``Roles.DoesNotExist`` for unknown roles rather than silently
  returning ``None``.

If a future refactor renames a role in the DB, these tests will fail and
force the constants to be updated in lockstep — preventing the silent
drift that motivated extracting this module in the first place.
"""

from django.test import TestCase

from apps.common.role_names import (
    ALL_ROLES,
    ROLE_ADMIN,
    ROLE_MENTOR,
    ROLE_STUDENT,
    ROLE_SUPERVISOR,
    get_role_by_name,
)
from apps.resources.models import Roles


class RoleNameConstantsTests(TestCase):
    def test_constants_are_lowercase_strings(self):
        for value in (ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_MENTOR, ROLE_STUDENT):
            self.assertIsInstance(value, str)
            self.assertEqual(value, value.lower())

    def test_all_roles_set_is_complete(self):
        self.assertEqual(
            ALL_ROLES,
            frozenset({ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_MENTOR, ROLE_STUDENT}),
        )

    def test_constant_values_match_seed_names(self):
        self.assertEqual(ROLE_ADMIN, "admin")
        self.assertEqual(ROLE_SUPERVISOR, "supervisor")
        self.assertEqual(ROLE_MENTOR, "mentor")
        self.assertEqual(ROLE_STUDENT, "student")


class GetRoleByNameTests(TestCase):
    def setUp(self):
        self.student_role = Roles.objects.create(role_name=ROLE_STUDENT)
        self.supervisor_role = Roles.objects.create(role_name=ROLE_SUPERVISOR)

    def test_returns_role_for_known_name(self):
        self.assertEqual(get_role_by_name(ROLE_STUDENT), self.student_role)
        self.assertEqual(get_role_by_name(ROLE_SUPERVISOR), self.supervisor_role)

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(get_role_by_name("STUDENT"), self.student_role)
        self.assertEqual(get_role_by_name("Supervisor"), self.supervisor_role)

    def test_unknown_role_raises_does_not_exist(self):
        with self.assertRaises(Roles.DoesNotExist):
            get_role_by_name("nonexistent-role")
