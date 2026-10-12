"""The database rule that two active groups in the same year can't share a
name, from 2026 on, and what each save path does when two admins hit it at
the same instant (both pass the friendly check, then the database refuses
the second)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.services.group import create_group, update_group
from apps.groups.models import Groups
from apps.groups.models.groups import UNIQUE_NAMES_FROM_YEAR
from apps.users.models import AdminScope

YEAR = UNIQUE_NAMES_FROM_YEAR


def _deleted(group):
    Groups.objects.filter(pk=group.pk).update(deleted_at=timezone.now())


class DatabaseRuleTests(TestCase):
    def assertRefused(self, name, year=YEAR):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Groups.objects.create(group_name=name, year=year)

    def test_the_same_name_twice_in_a_year_is_refused_ignoring_case_and_outer_spaces(self):
        Groups.objects.create(group_name="Team Alpha", year=YEAR)
        for name in ("Team Alpha", "team alpha", "  TEAM ALPHA "):
            with self.subTest(name=name):
                self.assertRefused(name)

    def test_earlier_years_other_years_and_deleted_groups_are_left_alone(self):
        # Before the rule's first year, old duplicates stay as they are.
        Groups.objects.create(group_name="Old Team", year=YEAR - 1)
        Groups.objects.create(group_name="Old Team", year=YEAR - 1)
        # The same name in two different years is fine.
        Groups.objects.create(group_name="Old Team", year=YEAR)
        # A deleted group's name can be used again.
        gone = Groups.objects.create(group_name="Gone Team", year=YEAR)
        _deleted(gone)
        Groups.objects.create(group_name="Gone Team", year=YEAR)
        self.assertEqual(Groups.objects.filter(group_name="Old Team").count(), 3)


class SameInstantSaveTests(TestCase):
    """Both saves pass ``duplicate_group_name_error`` (patched to say the name
    is free, as it would for both at the same instant); the database refuses
    the second, and the admin gets the usual message instead of an error."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(email="admin@example.com", password="x")
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.taken = Groups.objects.create(group_name="Team Alpha")
        self.message = f"A group named team alpha already exists in {self.taken.year}."

    def passes_check(self, module):
        return mock.patch(f"{module}.duplicate_group_name_error", return_value=None)

    def test_admin_create(self):
        with self.passes_check("apps.admin.services.group"):
            result = create_group("team alpha")
        self.assertEqual(result, {"msg": self.message, "data": None})
        self.assertEqual(Groups.objects.count(), 1)

    def test_admin_rename(self):
        other = Groups.objects.create(group_name="Team Beta")
        with self.passes_check("apps.admin.services.group"):
            result = update_group(str(other.id), name="team alpha")
        self.assertEqual(result, {"msg": self.message, "data": None})
        other.refresh_from_db()
        self.assertEqual(other.group_name, "Team Beta")

    def test_groups_api_create_and_rename(self):
        other = Groups.objects.create(group_name="Team Beta")
        with self.passes_check("apps.groups.serializers"):
            created = self.client.post(reverse("groups-list"), {"group_name": "team alpha"}, format="json")
            renamed = self.client.patch(
                reverse("groups-detail", args=[other.id]), {"group_name": "team alpha"}, format="json"
            )
        for response in (created, renamed):
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn(self.message, str(response.json()))
        self.assertEqual(Groups.objects.filter(group_name__iexact="team alpha").count(), 1)

    def test_groups_api_bulk_create_saves_none(self):
        with self.passes_check("apps.groups.views"):
            response = self.client.post(
                reverse("groups-bulk-create"),
                {"groups": [{"group_name": "Team Gamma"}, {"group_name": "team alpha"}]},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(self.message, str(response.json()))
        self.assertFalse(Groups.objects.filter(group_name="Team Gamma").exists())

    def test_restore(self):
        old = Groups.objects.create(group_name="Team Beta")
        _deleted(old)
        Groups.objects.filter(pk=old.pk).update(group_name="team alpha")
        with self.passes_check("apps.groups.views"):
            response = self.client.post(reverse("groups-restore", args=[old.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(f"{self.message} Rename one of them first.", str(response.json()))
        old.refresh_from_db()
        self.assertIsNotNone(old.deleted_at)


class AutoNameTests(TestCase):
    def test_moves_on_to_the_next_number_when_its_name_is_taken(self):
        Groups.objects.create(group_name="BTF01")
        # Typed in lower case, so the BTF numbering doesn't count it, but the
        # rule does: the auto name skips it.
        Groups.objects.create(group_name="btf02")
        self.assertEqual(Groups.create_auto_named().group_name, "BTF03")

    def test_another_group_taking_the_number_at_the_same_instant(self):
        Groups.objects.create(group_name="BTF01")
        # Both creators worked out BTF01 was next; this one saves second.
        with mock.patch("apps.groups.models.groups.allocate_group_number", return_value=1):
            self.assertEqual(Groups.create_auto_named().group_name, "BTF02")
