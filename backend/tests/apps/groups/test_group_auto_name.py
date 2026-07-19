from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.groups.models import Groups
from apps.users.models import AdminScope


def soft_delete(group):
    """Tombstone a group, backdating created_at for the deleted_at >= created_at CHECK."""
    now = timezone.now()
    Groups.objects.filter(id=group.id).update(
        created_at=now - timedelta(days=1), deleted_at=now,
    )


class CreateAutoNamedTests(TestCase):
    def test_series_starts_at_one_and_increments_by_one(self):
        names = [Groups.create_auto_named().group_name for _ in range(3)]
        self.assertEqual(names, ["BTF1", "BTF2", "BTF3"])

    def test_auto_name_is_persisted(self):
        group = Groups.create_auto_named()
        group.refresh_from_db()
        self.assertEqual(group.group_name, "BTF1")

    def test_soft_deleted_number_is_never_reused(self):
        groups = [Groups.create_auto_named() for _ in range(3)]
        soft_delete(groups[1])

        self.assertEqual(Groups.create_auto_named().group_name, "BTF4")

    def test_hand_named_squatter_is_stepped_over(self):
        Groups.objects.create(group_name="BTF5")

        self.assertEqual(Groups.create_auto_named().group_name, "BTF6")

    def test_legacy_names_do_not_feed_the_counter(self):
        # Old pk-derived names were never migrated; they don't match ^BTF[0-9]+$.
        Groups.objects.create(group_name="BTF_0042")
        Groups.objects.create(group_name="BTF_C0007")
        Groups.objects.create(group_name="Team Alpha")

        self.assertEqual(Groups.create_auto_named().group_name, "BTF1")

    def test_hard_deleting_the_highest_group_releases_its_number(self):
        # The counter is "highest existing + 1"; only the top number comes back.
        groups = [Groups.create_auto_named() for _ in range(3)]
        groups[2].delete()

        self.assertEqual(Groups.create_auto_named().group_name, "BTF3")

    def test_wide_hand_named_squatter_does_not_wedge_the_counter(self):
        # A fixed pad width would truncate this and hand back a name already taken.
        Groups.objects.create(group_name="BTF999999999999")

        self.assertEqual(Groups.create_auto_named().group_name, "BTF1000000000000")
        self.assertEqual(Groups.create_auto_named().group_name, "BTF1000000000001")

    def test_marker_argument_is_gone(self):
        with self.assertRaises(TypeError):
            Groups.create_auto_named(marker="C")


class GroupCreateApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_user(
            email="autoname-admin@example.com", password="adminpass",
        )
        AdminScope.objects.create(user=self.admin_user)
        self.client.force_authenticate(user=self.admin_user)
        self.group = Groups.objects.create(group_name="Group One")
        self.list_url = reverse("groups-list")
        self.detail_url = reverse("groups-detail", args=[self.group.id])

    def _rows(self, resp):
        body = resp.json()
        return body["results"] if isinstance(body, dict) and "results" in body else body

    # --- create -------------------------------------------------------------
    def test_blank_name_on_create_auto_generates(self):
        resp = self.client.post(self.list_url, {"group_name": ""}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["group_name"], "BTF1")

    def test_omitted_name_on_create_auto_generates(self):
        resp = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["group_name"], "BTF1")

    def test_create_steps_over_a_hand_named_squatter(self):
        Groups.objects.create(group_name="BTF5")

        resp = self.client.post(self.list_url, {"group_name": ""}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["group_name"], "BTF6")

    # --- list ordering ------------------------------------------------------
    def test_list_orders_auto_names_numerically(self):
        # Without the virtual zero-padding "BTF10" would sort before "BTF9".
        for name in ("BTF10", "BTF9", "BTF100", "BTF2"):
            Groups.objects.create(group_name=name)

        resp = self.client.get(self.list_url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [row["group_name"] for row in self._rows(resp)]
        self.assertEqual(
            [name for name in names if name.startswith("BTF")],
            ["BTF2", "BTF9", "BTF10", "BTF100"],
        )

    # --- update (FIX 1 / FIX 2) --------------------------------------------
    def test_patch_blank_name_returns_400(self):
        for blank in ("", "   "):
            with self.subTest(name=blank):
                resp = self.client.patch(
                    self.detail_url, {"group_name": blank}, format="json",
                )
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
                self.group.refresh_from_db()
                self.assertEqual(self.group.group_name, "Group One")

    def test_put_blank_name_returns_400(self):
        resp = self.client.put(self.detail_url, {"group_name": ""}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.group.refresh_from_db()
        self.assertEqual(self.group.group_name, "Group One")

    def test_put_without_name_returns_400(self):
        resp = self.client.put(self.detail_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("group_name", str(resp.json()))
        self.group.refresh_from_db()
        self.assertEqual(self.group.group_name, "Group One")

    def test_put_with_name_still_renames(self):
        resp = self.client.put(
            self.detail_url, {"group_name": "Replaced"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.group.refresh_from_db()
        self.assertEqual(self.group.group_name, "Replaced")

    def test_patch_without_name_is_still_a_valid_no_op(self):
        resp = self.client.patch(self.detail_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.group.refresh_from_db()
        self.assertEqual(self.group.group_name, "Group One")

    # --- bulk create (FIX 7) ------------------------------------------------
    def test_bulk_create_duplicate_name_returns_400(self):
        url = reverse("groups-bulk-create")
        resp = self.client.post(
            url, {"groups": [{"group_name": "Group One"}]}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Groups.objects.filter(group_name="Group One").count(), 1)

    def test_bulk_create_duplicate_within_payload_returns_400(self):
        url = reverse("groups-bulk-create")
        resp = self.client.post(
            url,
            {"groups": [{"group_name": "Twice"}, {"group_name": "Twice"}]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Groups.objects.filter(group_name="Twice").exists())

    def test_bulk_create_reuses_a_soft_deleted_name(self):
        dead = Groups.objects.create(group_name="Recycled")
        soft_delete(dead)

        url = reverse("groups-bulk-create")
        resp = self.client.post(
            url, {"groups": [{"group_name": "Recycled"}]}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_bulk_create_steps_over_a_hand_named_squatter(self):
        Groups.objects.create(group_name="BTF5")
        url = reverse("groups-bulk-create")

        resp = self.client.post(url, {"groups": [{"group_name": ""}]}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()[0]["group_name"], "BTF6")

    def test_bulk_create_auto_names_blank_entries(self):
        url = reverse("groups-bulk-create")
        resp = self.client.post(
            url, {"groups": [{"group_name": ""}, {}]}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            [row["group_name"] for row in resp.json()], ["BTF1", "BTF2"],
        )
