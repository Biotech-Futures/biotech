"""Notify Finalists' announcement: the finalist email's wording until edited,
posted in the app to the finalist groups that have been emailed."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.announcements.models import Announcement, AnnouncementAudience
from apps.grading.models import FinalistFlag
from apps.groups.models.groups import Groups
from apps.management.models import FinalistAnnouncement, FinalistEmailSettings
from apps.management.services.finalist_announcement import as_announcement
from apps.management.services.finalist_notify import _long_date
from apps.services.models import SystemEmailTemplate

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
        # The email's body: to every finalist, its box, headings, lists and
        # Register button kept, its footer gone.
        self.assertTrue(body["body"].startswith("<p>Dear finalists,</p>"), body["body"][:80])
        self.assertIn('<div style="', body["body"])
        self.assertIn("<h2>Please confirm attendance</h2><ul><li>", body["body"])
        self.assertIn('<a class="cta-link" href="https://events.example.com/symposium"', body["body"])
        self.assertIn("reply to the finalist email we sent you", body["body"])
        self.assertNotIn("receiving this email", body["body"])
        # The title isn't repeated at the top.
        self.assertNotIn("<h1", body["body"])

    def test_it_follows_the_emails_wording_from_system_emails(self):
        SystemEmailTemplate.objects.create(
            key="finalist_notification",
            body_html="<h1>Well done</h1><p>Dear members of <strong>{{ group_name }}</strong>,</p>"
            "<p>See you on {{ symposium_date }}.</p>",
        )
        date = _long_date(FinalistEmailSettings.load().symposium_date)
        self.assertEqual(self._get()["body"], f"<p>Dear finalists,</p><p>See you on {date}.</p>")

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
        # What it keeps is cleaned, as System Emails' bodies are.
        r = self.client.patch(
            reverse(URL), {"title": "Hi", "body": '<p onclick="x()">Hi<script>x()</script></p>'}, format="json",
        )
        self.assertEqual(r.json()["body"], "<p>Hi</p>")
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


class AnnouncementCategoriesTests(_GradingFixture):
    """New Announcement's Finalist, Nonfinalist and Nonsubmission categories."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def _get(self):
        r = self.client.get(reverse("management:announcement-categories"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        return r.json()

    def test_they_wait_for_the_deadline_and_its_grace_hours(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.submissions.models import Deadline

        Deadline.objects.update(is_active=False)
        Deadline.objects.create(closes_at=timezone.now() - timedelta(hours=1), grace_hours=2, is_active=True)
        body = self._get()
        self.assertFalse(body["available"])
        self.assertIn("Available once submissions close, on", body["reason"])
        self.assertEqual([c["label"] for c in body["categories"]], ["Finalist", "Nonfinalist", "Nonsubmission"])
        self.assertEqual({tuple(c["group_ids"]) for c in body["categories"]}, {()})

    def test_once_closed_each_lists_its_groups(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.submissions.models import Deadline
        from apps.users.models import User

        from tests.apps.management.test_symposium_emails import _member, _submitted_team

        # Closed, grace hours and all.
        Deadline.objects.update(is_active=False)
        Deadline.objects.create(closes_at=timezone.now() - timedelta(hours=3), grace_hours=2, is_active=True)

        # The fixture's submitted team is a finalist; another submitted isn't;
        # a third, with a student, never submitted.
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        other = _submitted_team("Other", self.staff)
        quiet = Groups.objects.create(group_name="Quiet")
        _member("q@example.com", quiet)
        self.assertTrue(User.objects.filter(email="q@example.com").exists())

        body = self._get()
        self.assertTrue(body["available"])
        ids = {c["key"]: c["group_ids"] for c in body["categories"]}
        self.assertEqual(ids["finalists"], [self.group.id])
        self.assertEqual(ids["nonfinalists"], [other.id])
        self.assertIn(quiet.id, ids["nonsubmissions"])
        self.assertNotIn(self.group.id, ids["nonsubmissions"])

    def test_it_is_for_staff_only(self):
        self.client.force_authenticate(self.non_staff)
        r = self.client.get(reverse("management:announcement-categories"))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class AsAnnouncementTests(_GradingFixture):
    def test_it_drops_the_title_tidies_the_indenting_and_keeps_only_box_and_button_styles(self):
        html = """
            <h1 style="color:#017151">Title</h1>
            <p style="color:#153226; font-size:16px">
              Dear members of <strong>finalists</strong>,
            </p>
            <div style="border:1px dashed #017151; background:#e9f6f1; position:fixed">
              <strong style="color:#017151;">Important:</strong> on <strong>Friday</strong>.
            </div>
            <ul style="margin:0"><li style="margin:6px 0;">Have one reply to this email.</li></ul>
            <div style="margin:16px 0;"><a class="cta-link" href="https://x.org/r" style="background:#017151; color:#ffffff">
              Register
            </a></div>
            <script>x()</script>
        """
        self.assertEqual(
            as_announcement(html),
            "<p>Dear finalists,</p>"
            '<div style="border:1px dashed #017151;background-color:#e9f6f1">'
            "<strong>Important:</strong> on <strong>Friday</strong>.</div>"
            "<ul><li>Have one reply to the finalist email we sent you.</li></ul>"
            '<div style="margin:16px 0"><a class="cta-link" href="https://x.org/r"'
            ' style="background-color:#017151;color:#ffffff"'
            ' rel="noopener noreferrer">Register</a></div>',
        )
