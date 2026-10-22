"""Management > Challenge Start > Release Resources: a resource shown is
everyone's now; hidden, it's theirs from its release date (the start of that
day, Sydney time), or not at all without one. Admins always have it. Each
year's release is kept, for next year's Last released."""
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.resources.models import ResourceRelease, Resources
from apps.resources.release import SYDNEY, release_moment, sydney_today
from apps.users.models import AdminScope

LIST_URL = "/api/v1/management/resource-releases/"


def row_url(resource):
    return f"{LIST_URL}{resource.pk}/"


class ResourceReleaseTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.admin = users.create_user(email="admin-release@example.com", password="pw12345!")
        AdminScope.objects.create(user=self.admin)
        self.student = users.create_user(email="student-release@example.com", password="pw12345!")
        self.resource = self.make("Ethics primer")
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.student_client = APIClient()
        self.student_client.force_authenticate(self.student)

    def make(self, name, **fields):
        return Resources.objects.create(
            name=name, description=name, uploaded_by=self.admin,
            visibility_scope=Resources.VisibilityScope.PUBLIC, storage_key=f"https://example.com/{name}.pdf",
            **fields,
        )

    def patch(self, **change):
        response = self.admin_client.patch(row_url(self.resource), change, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.resource.refresh_from_db()
        return response.json()

    def student_sees(self) -> bool:
        names = [item["name"] for item in self.student_client.get(reverse("resource-files-list")).json()["results"]]
        opened = self.student_client.get(reverse("resource-files-detail", kwargs={"pk": self.resource.pk}))
        self.assertEqual("Ethics primer" in names, opened.status_code == 200)
        return "Ethics primer" in names

    def test_shown_until_hidden_and_admins_always_see_it(self):
        self.assertTrue(self.student_sees())
        row = self.patch(shown=False)
        self.assertEqual((row["shown"], row["released"]), (False, False))
        self.assertFalse(self.student_sees())
        self.assertEqual(
            self.admin_client.get(reverse("resource-files-detail", kwargs={"pk": self.resource.pk})).status_code, 200,
        )

    def test_hidden_with_a_date_appears_from_the_start_of_that_day_sydney_time(self):
        self.patch(shown=False)
        tomorrow = sydney_today() + timedelta(days=1)
        self.patch(release_on=tomorrow.isoformat())
        self.assertFalse(self.student_sees())
        # Its release kept, to come, at the start of the day in Sydney.
        release = ResourceRelease.objects.get(resource=self.resource)
        self.assertEqual(release.released_at, release_moment(tomorrow))
        self.assertEqual(release.released_at.astimezone(SYDNEY).hour, 0)

        row = self.patch(release_on=sydney_today().isoformat())
        self.assertTrue(row["released"])
        self.assertTrue(self.student_sees())

    def test_showing_releases_it_now_and_drops_a_date_to_come(self):
        self.patch(shown=False, release_on=(sydney_today() + timedelta(days=10)).isoformat())
        before = timezone.now()
        self.patch(shown=True)
        release = ResourceRelease.objects.get(resource=self.resource)
        self.assertGreaterEqual(release.released_at, before)
        self.assertLessEqual(release.released_at, timezone.now())

    def test_clearing_a_date_to_come_drops_its_release(self):
        self.patch(shown=False, release_on=(sydney_today() + timedelta(days=3)).isoformat())
        self.patch(release_on=None)
        self.assertFalse(ResourceRelease.objects.exists())
        self.assertFalse(self.student_sees())

    def test_hiding_after_its_date_came_takes_the_date_away_too(self):
        self.patch(shown=False, release_on=(sydney_today() - timedelta(days=1)).isoformat())
        self.assertTrue(self.student_sees())
        row = self.patch(shown=False)
        self.assertEqual((row["release_on"], row["released"]), (None, False))
        self.assertFalse(self.student_sees())

    def test_lists_resources_by_name_with_last_years_release_not_attachments_or_deleted(self):
        last_year = sydney_today().year - 1
        ResourceRelease.objects.create(
            resource=self.resource, year=last_year,
            released_at=datetime(last_year, 2, 12, tzinfo=SYDNEY),
        )
        self.make("Attachment", kind=Resources.ResourceKind.ATTACHMENT)
        self.make("Gone", deleted_at=timezone.now())
        self.make("Brainstorm guide")
        rows = self.admin_client.get(LIST_URL).json()["resources"]
        self.assertEqual([row["name"] for row in rows], ["Brainstorm guide", "Ethics primer"])
        self.assertIsNone(rows[0]["last_released_at"])
        self.assertTrue(rows[1]["last_released_at"].startswith(f"{last_year}-02-1"))
        self.assertEqual((rows[1]["shown"], rows[1]["release_on"], rows[1]["released"]), (True, None, True))
        # What its icon is drawn from, as the Resources page's.
        self.assertIn("kind", rows[0])
        self.assertIn("file_mime_type", rows[0])

    def test_admins_only_and_values_checked(self):
        self.assertEqual(self.student_client.get(LIST_URL).status_code, 403)
        self.assertEqual(self.student_client.patch(row_url(self.resource), {"shown": False}, format="json").status_code, 403)
        for change in ({}, {"shown": "no"}, {"release_on": "next week"}):
            with self.subTest(change=change):
                self.assertEqual(self.admin_client.patch(row_url(self.resource), change, format="json").status_code, 400)
        self.assertEqual(self.admin_client.patch(f"{LIST_URL}99999/", {"shown": True}, format="json").status_code, 404)
