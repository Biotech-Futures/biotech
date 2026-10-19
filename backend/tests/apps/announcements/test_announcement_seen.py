"""An announcement published from now on is New to someone until they open
it (its card, its title, or expand it), which POST {id}/seen/ records; their
own never is, and nor is one published before New existed."""
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.announcements.models import Announcement, AnnouncementSeen
from apps.users.models import User

LIST_URL = "/announcements/v1/"


def _items(response):
    body = response.json()
    return body["results"] if isinstance(body, dict) else body


class AnnouncementSeenTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="author@example.com", password="testpass")
        self.reader = User.objects.create_user(email="ada@example.com", password="testpass")
        self.announcement = Announcement.objects.create(
            author_user=self.author,
            title="Welcome",
            body="<p>Hello.</p>",
            visibility_scope=Announcement.VisibilityScope.GLOBAL,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.reader)

    def _is_new(self):
        row = next(item for item in _items(self.client.get(LIST_URL)) if item["id"] == self.announcement.id)
        return row["is_new"]

    def test_it_is_new_until_opened(self):
        self.assertTrue(self._is_new())
        self.assertTrue(self.client.get(f"{LIST_URL}{self.announcement.id}/").json()["is_new"])

        response = self.client.post(f"{LIST_URL}{self.announcement.id}/seen/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(self._is_new())
        self.assertFalse(self.client.get(f"{LIST_URL}{self.announcement.id}/").json()["is_new"])

    def test_opening_it_again_is_recorded_once(self):
        for _ in range(2):
            self.assertEqual(
                self.client.post(f"{LIST_URL}{self.announcement.id}/seen/").status_code,
                status.HTTP_204_NO_CONTENT,
            )
        self.assertEqual(AnnouncementSeen.objects.filter(user=self.reader).count(), 1)

    def test_it_is_new_to_each_person_separately(self):
        self.client.post(f"{LIST_URL}{self.announcement.id}/seen/")
        other = APIClient()
        other.force_authenticate(User.objects.create_user(email="bo@example.com", password="testpass"))
        row = next(item for item in _items(other.get(LIST_URL)) if item["id"] == self.announcement.id)
        self.assertTrue(row["is_new"])

    def test_your_own_announcement_is_never_new(self):
        self.client.force_authenticate(self.author)
        self.assertFalse(self._is_new())

    def test_one_published_before_new_existed_is_never_new(self):
        # As the migration leaves every announcement already published.
        self.announcement.shows_new = False
        self.announcement.save(update_fields=["shows_new"])
        self.assertFalse(self._is_new())

    def test_a_new_one_shows_new_by_default(self):
        self.assertTrue(Announcement.objects.create(
            author_user=self.author, title="Later", body="<p>Hi.</p>",
            visibility_scope=Announcement.VisibilityScope.GLOBAL,
        ).shows_new)

    def test_one_you_cannot_see_cannot_be_marked(self):
        self.announcement.archived_at = timezone.now()
        self.announcement.save(update_fields=["archived_at"])
        response = self.client.post(f"{LIST_URL}{self.announcement.id}/seen/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(AnnouncementSeen.objects.exists())
