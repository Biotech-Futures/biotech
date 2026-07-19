from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.groups.models import GroupAutoNameUnavailable, Groups
from apps.users.models import AdminScope

PLACEHOLDER_PREFIX = "BTF_new-"


def squat_next_auto_name(marker: str = "") -> str:
    """Hand-name a group into the slot the next auto-named group would claim.

    The probe row consumes a pk itself, so the next insert lands at ``probe + 2``.
    """
    probe = Groups.objects.create(group_name="collision-probe")
    name = f"BTF_{marker}{probe.id + 2:04d}"
    Groups.objects.create(group_name=name)
    return name


class CreateAutoNamedTests(TestCase):
    def test_auto_name_is_pk_derived_and_zero_padded(self):
        group = Groups.create_auto_named()
        self.assertEqual(group.group_name, f"BTF_{group.id:04d}")
        group.refresh_from_db()
        self.assertEqual(group.group_name, f"BTF_{group.id:04d}")

    def test_marker_is_embedded_before_the_pk(self):
        group = Groups.create_auto_named(marker="C")
        self.assertEqual(group.group_name, f"BTF_C{group.id:04d}")

    def test_taken_slot_raises_instead_of_keeping_the_placeholder(self):
        squatted = squat_next_auto_name()
        with self.assertRaises(GroupAutoNameUnavailable) as ctx:
            Groups.create_auto_named()
        self.assertIn(squatted, str(ctx.exception))

    def test_taken_slot_leaves_no_orphan_placeholder_row(self):
        squat_next_auto_name()
        before = set(Groups.objects.values_list("id", flat=True))

        with self.assertRaises(GroupAutoNameUnavailable):
            Groups.create_auto_named()

        self.assertEqual(set(Groups.objects.values_list("id", flat=True)), before)
        self.assertFalse(
            Groups.objects.filter(group_name__startswith=PLACEHOLDER_PREFIX).exists()
        )

    def test_soft_deleted_squatter_does_not_block_the_slot(self):
        # Uniqueness only covers active groups, so a tombstoned name must not collide.
        probe = Groups.objects.create(group_name="collision-probe")
        taken = Groups.objects.create(group_name=f"BTF_{probe.id + 2:04d}")
        Groups.objects.filter(id=taken.id).update(deleted_at=taken.created_at)

        group = Groups.create_auto_named()
        self.assertEqual(group.group_name, f"BTF_{group.id:04d}")


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

    # --- create -------------------------------------------------------------
    def test_blank_name_on_create_auto_generates(self):
        resp = self.client.post(self.list_url, {"group_name": ""}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        body = resp.json()
        self.assertEqual(body["group_name"], f"BTF_{body['id']:04d}")

    def test_omitted_name_on_create_auto_generates(self):
        resp = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        body = resp.json()
        self.assertEqual(body["group_name"], f"BTF_{body['id']:04d}")

    def test_auto_name_collision_on_create_returns_400_not_a_uuid_name(self):
        squat_next_auto_name()
        resp = self.client.post(self.list_url, {"group_name": ""}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Groups.objects.filter(group_name__startswith=PLACEHOLDER_PREFIX).exists()
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
        Groups.objects.filter(id=dead.id).update(deleted_at=dead.created_at)

        url = reverse("groups-bulk-create")
        resp = self.client.post(
            url, {"groups": [{"group_name": "Recycled"}]}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_bulk_create_auto_name_collision_returns_400(self):
        squat_next_auto_name()
        url = reverse("groups-bulk-create")
        resp = self.client.post(url, {"groups": [{"group_name": ""}]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Groups.objects.filter(group_name__startswith=PLACEHOLDER_PREFIX).exists()
        )

    def test_bulk_create_auto_names_blank_entries(self):
        url = reverse("groups-bulk-create")
        resp = self.client.post(
            url, {"groups": [{"group_name": ""}, {}]}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        for row in resp.json():
            self.assertEqual(row["group_name"], f"BTF_{row['id']:04d}")
