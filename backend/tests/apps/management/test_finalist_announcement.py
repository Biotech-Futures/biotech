"""Notify Finalists' announcement: the finalist email's wording until edited,
posted in the app to the finalist groups that have been emailed."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.announcements.models import Announcement, AnnouncementAudience
from apps.grading.models import FinalistFlag
from apps.groups.models.groups import Groups
from apps.management.models import FinalistAnnouncement
from apps.management.services.finalist_announcement import text_to_html

from tests.apps.grading.fixtures import _GradingFixture
from tests.apps.management.test_finalist_emails import _set_email_details

URL = "management:finalist-announcement"
POST = "management:finalist-announcement-post"


class FinalistAnnouncementTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        _set_email_details()

    def _get(self):
        return self.client.get(reverse(URL)).json()

    def test_it_starts_as_the_finalist_emails_wording(self):
        body = self._get()
        self.assertEqual(body["title"], "Congratulations – You’re a BIOTech Futures Finalist!")
        self.assertFalse(body["edited"])
        # The email's text as paragraphs and lists, its link live, its footer gone.
        self.assertIn("<p>Dear members of our finalist teams,</p>", body["body"])
        self.assertIn("<ul><li>", body["body"])
        self.assertIn('<a href="https://events.example.com/symposium">', body["body"])
        self.assertNotIn("receiving this email", body["body"])
        # Not the title again at the top.
        self.assertFalse(body["body"].startswith("<p>Congratulations"))

    def test_edited_wording_is_kept(self):
        r = self.client.patch(reverse(URL), {"title": "Finalists!", "body": "<p>Well done.</p>"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual((r.json()["title"], r.json()["body"], r.json()["edited"]), ("Finalists!", "<p>Well done.</p>", True))
        self.assertEqual(self._get()["title"], "Finalists!")
        # Restore default goes back to the email's wording.
        r = self.client.delete(reverse(URL))
        self.assertEqual((r.json()["title"], r.json()["edited"]), (
            "Congratulations \u2013 You\u2019re a BIOTech Futures Finalist!", False,
        ))
        # An empty title or body is refused.
        r = self.client.patch(reverse(URL), {"title": "Hi", "body": "<p></p>"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_posts_to_the_groups_emailed_and_posting_again_updates_it(self):
        other = Groups.objects.create(group_name="BTF-LATER")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff, notified=True)
        FinalistFlag.objects.create(group=other, flagged_by=self.staff, notified=False)
        self.assertEqual(self._get()["groups"], 1)

        r = self.client.post(reverse(POST))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertIsNotNone(r.json()["posted_at"])
        announcement = Announcement.objects.get()
        self.assertEqual(announcement.title, "Congratulations – You’re a BIOTech Futures Finalist!")
        groups = lambda: set(AnnouncementAudience.objects.values_list("group_id", flat=True))  # noqa: E731
        # Only the group that has been emailed sees it.
        self.assertEqual(groups(), {self.group.id})

        # Once the other is emailed, posting again updates the same one.
        FinalistFlag.objects.filter(group=other).update(notified=True)
        self.client.patch(reverse(URL), {"title": "Finalists!", "body": "<p>Well done.</p>"}, format="json")
        self.client.post(reverse(POST))
        self.assertEqual(Announcement.objects.count(), 1)
        self.assertEqual(Announcement.objects.get().title, "Finalists!")
        self.assertEqual(groups(), {self.group.id, other.id})
        self.assertEqual(FinalistAnnouncement.load().announcement_id, announcement.id)

    def test_an_archived_announcement_is_posted_afresh(self):
        from django.utils import timezone

        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff, notified=True)
        self.client.post(reverse(POST))
        Announcement.objects.update(archived_at=timezone.now())
        self.client.post(reverse(POST))
        self.assertEqual(Announcement.objects.filter(archived_at__isnull=True).count(), 1)

    def test_nothing_is_posted_before_any_group_is_emailed(self):
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff, notified=False)
        r = self.client.post(reverse(POST))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.json()["detail"], "No finalist group has been emailed yet.")
        self.assertFalse(Announcement.objects.exists())

    def test_it_is_for_staff_only(self):
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(self.client.get(reverse(URL)).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(reverse(POST)).status_code, status.HTTP_403_FORBIDDEN)


class TextToHtmlTests(_GradingFixture):
    def test_paragraphs_lists_and_links(self):
        text = "Title\n\nHello\nthere.\n\nDO THIS\n  - one\n    more\n  - two https://x.org/a.\n\nBye\n--\nfooter"
        self.assertEqual(
            text_to_html(text, "Title"),
            '<p>Hello there.</p><p>DO THIS</p><ul><li>one more</li>'
            '<li>two <a href="https://x.org/a">https://x.org/a</a>.</li></ul><p>Bye</p>',
        )
        # Its text is escaped.
        self.assertEqual(text_to_html("a <b> & c"), "<p>a &lt;b&gt; &amp; c</p>")
