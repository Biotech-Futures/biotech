"""The announcements that go with the outcome emails: each its email's
wording until edited, posted in the app to whoever the email has reached."""
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.announcements.models import Announcement, AnnouncementAudience
from apps.grading.models import FinalistFlag
from apps.groups.models.groups import Groups
from apps.admin.services.announcement import update_announcement
from apps.management.models import FinalistEmailSettings, OutcomeAnnouncement
from apps.management.services import outcome_announcement
from apps.management.services.outcome_announcement import NAME, as_announcement
from apps.management.services.finalist_notify import _long_date
from apps.services.models import SystemEmailTemplate

from tests.apps.grading.fixtures import _GradingFixture
from tests.apps.management.test_finalist_emails import _set_email_details



def _url(kind="finalists"):
    return reverse("management:outcome-announcement", args=[kind])


def _post_url(kind="finalists"):
    return reverse("management:outcome-announcement-post", args=[kind])


class FinalistAnnouncementTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        _set_email_details()

    def _get(self):
        return self.client.get(_url()).json()

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
        self.assertIn("reply to the email we sent you", body["body"])
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
        r = self.client.patch(_url(), {"title": "Finalists!", "body": "<p>Well done.</p>"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual((r.json()["title"], r.json()["body"], r.json()["edited"]), ("Finalists!", "<p>Well done.</p>", True))
        self.assertEqual(self._get()["title"], "Finalists!")
        # Restore default goes back to the email's wording.
        r = self.client.delete(_url())
        self.assertEqual((r.json()["title"], r.json()["edited"]), (
            "Congratulations \u2013 You\u2019re a BIOTech Futures Finalist!", False,
        ))
        # What it keeps is cleaned, as System Emails' bodies are.
        r = self.client.patch(
            _url(), {"title": "Hi", "body": '<p onclick="x()">Hi<script>x()</script></p>'}, format="json",
        )
        self.assertEqual(r.json()["body"], "<p>Hi</p>")
        # An empty title or body is refused.
        r = self.client.patch(_url(), {"title": "Hi", "body": "<p></p>"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_posts_to_the_groups_emailed_and_posting_again_updates_it(self):
        other = Groups.objects.create(group_name="BTF-LATER")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff, notified=True)
        FinalistFlag.objects.create(group=other, flagged_by=self.staff, notified=False)
        self.assertEqual((self._get()["recipients"], self._get()["noun"]), (1, "finalist group"))

        r = self.client.post(_post_url())
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertIsNotNone(r.json()["posted_at"])
        announcement = Announcement.objects.get()
        self.assertEqual(announcement.title, "Congratulations – You’re a BIOTech Futures Finalist!")
        groups = lambda: set(AnnouncementAudience.objects.values_list("group_id", flat=True))  # noqa: E731
        # Only the group that has been emailed sees it.
        self.assertEqual(groups(), {self.group.id})

        # Once the other is emailed, posting again updates the same one.
        FinalistFlag.objects.filter(group=other).update(notified=True)
        self.client.patch(_url(), {"title": "Finalists!", "body": "<p>Well done.</p>"}, format="json")
        self.client.post(_post_url())
        self.assertEqual(Announcement.objects.count(), 1)
        self.assertEqual(Announcement.objects.get().title, "Finalists!")
        self.assertEqual(groups(), {self.group.id, other.id})
        self.assertEqual(OutcomeAnnouncement.objects.get(key="finalists").announcement_id, announcement.id)

    def test_it_counts_a_group_someone_on_was_reached(self):
        from apps.management.models import EmailDelivery

        from tests.apps.management.test_symposium_emails import _member

        # Emailed, but someone on it was missed: not notified, yet reached.
        partly = Groups.objects.create(group_name="BTF-PARTLY")
        reached = _member("amy@example.com", partly)
        _member("missed@example.com", partly)
        FinalistFlag.objects.create(group=partly, flagged_by=self.staff, notified=False)
        EmailDelivery.objects.create(email="finalist_notification", group=partly, address=reached.email)
        # Never emailed.
        quiet = Groups.objects.create(group_name="BTF-QUIET")
        FinalistFlag.objects.create(group=quiet, flagged_by=self.staff, notified=False)

        self.assertEqual(self._get()["recipients"], 1)
        self.client.post(_post_url())
        self.assertEqual(list(AnnouncementAudience.objects.values_list("group_id", flat=True)), [partly.id])

    def test_an_archived_announcement_is_posted_afresh(self):
        from django.utils import timezone

        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff, notified=True)
        self.client.post(_post_url())
        Announcement.objects.update(archived_at=timezone.now())
        self.client.post(_post_url())
        self.assertEqual(Announcement.objects.filter(archived_at__isnull=True).count(), 1)

    def test_nothing_is_posted_before_any_group_is_emailed(self):
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff, notified=False)
        r = self.client.post(_post_url())
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            r.json()["detail"], "No finalist group has been emailed yet. It can be posted once its email has been sent.",
        )
        self.assertEqual(self._get()["blocked"], r.json()["detail"])
        self.assertFalse(Announcement.objects.exists())

    def test_nothing_is_posted_while_submissions_are_open(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.submissions.models import Deadline

        # Even with a group marked as emailed: its email can't have gone yet.
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff, notified=True)
        Deadline.objects.update(is_active=False)
        Deadline.objects.create(closes_at=timezone.now() - timedelta(hours=1), grace_hours=2, is_active=True)
        # As the send buttons say it, with Post for Send.
        reason = self._get()["blocked"]
        self.assertRegex(reason, r"^Submissions are open until .+ \(Sydney time\)\. Post this once they close\.$")
        r = self.client.post(_post_url())
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.json()["detail"], reason)
        self.assertFalse(Announcement.objects.exists())

        # Once closed, grace hours and all, it can.
        Deadline.objects.update(closes_at=timezone.now() - timedelta(hours=3))
        self.assertEqual(self._get()["blocked"], "")
        self.assertEqual(self.client.post(_post_url()).status_code, status.HTTP_200_OK)

    def test_it_is_for_staff_only(self):
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(self.client.get(_url()).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(_post_url()).status_code, status.HTTP_403_FORBIDDEN)

    def test_an_unknown_kind_is_not_found(self):
        self.assertEqual(self.client.get(_url("everyone")).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(_post_url("everyone")).status_code, status.HTTP_404_NOT_FOUND)


class OtherOutcomeAnnouncementTests(_GradingFixture):
    """The non-finalist, non-submission and results emails' announcements."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        _set_email_details()

    def test_each_starts_as_its_emails_wording(self):
        nonfinalist = self.client.get(_url("nonfinalists")).json()
        self.assertEqual(nonfinalist["title"], "Thank you for your submission \u2013 Invitation to the Symposium")
        self.assertTrue(nonfinalist["body"].startswith("<p>Dear participants,</p>"), nonfinalist["body"][:80])
        self.assertEqual(nonfinalist["noun"], "nonfinalist group")
        self.assertIn("Dear participants,", self.client.get(_url("nonsubmissions")).json()["body"])
        # The results emails' attachments are in the email, not here.
        groups = self.client.get(_url("results-groups")).json()["body"]
        self.assertIn("Dear participants,", groups)
        self.assertIn("In the email we sent you, you\u2019ll find merit certificates", groups)
        supervisors = self.client.get(_url("results-supervisors")).json()
        self.assertIn("Dear supervisors,", supervisors["body"])
        self.assertIn("In the email we sent you, you will find", supervisors["body"])
        self.assertIn("by replying to the email we sent you", supervisors["body"])
        self.assertEqual(supervisors["noun"], "supervisor")
        # Each has its own wording.
        self.client.patch(_url("nonsubmissions"), {"title": "Hi", "body": "<p>Hi.</p>"}, format="json")
        self.assertEqual(self.client.get(_url("nonsubmissions")).json()["title"], "Hi")
        self.assertNotEqual(self.client.get(_url("nonfinalists")).json()["title"], "Hi")

    def test_a_team_email_posts_to_the_groups_someone_on_was_reached(self):
        reached = Groups.objects.create(group_name="BTF-REACHED")
        missed = Groups.objects.create(group_name="BTF-MISSED")
        teams = SimpleNamespace(emailed={self.group.id}, reached={reached.id: {1}, missed.id: set()})
        with mock.patch.object(outcome_announcement.symposium_emails, "audience", return_value=teams):
            r = self.client.post(_post_url("nonfinalists"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(
            set(AnnouncementAudience.objects.values_list("group_id", flat=True)), {self.group.id, reached.id},
        )

    def test_the_supervisor_email_posts_to_those_supervisors_only(self):
        users = get_user_model().objects
        emailed = users.create_user(email="sup1@example.com", password="pw12345!")
        not_yet = users.create_user(email="sup2@example.com", password="pw12345!")
        result = SimpleNamespace(supervisors_emailed={emailed.id})
        with mock.patch.object(outcome_announcement.results_notify, "results_audience", return_value=result):
            self.assertEqual(self.client.get(_url("results-supervisors")).json()["recipients"], 1)
            r = self.client.post(_post_url("results-supervisors"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(list(AnnouncementAudience.objects.values_list("user_id", flat=True)), [emailed.id])

        # The supervisor emailed sees it; another doesn't.
        def seen(user):
            client = APIClient()
            client.force_authenticate(user)
            body = client.get(reverse("announcements-list")).json()
            return body["results"] if isinstance(body, dict) else body

        self.assertEqual(len(seen(emailed)), 1)
        self.assertEqual(seen(not_yet), [])

        # Saving it from New Announcement, which shows only roles and groups,
        # keeps them, so it doesn't become everyone's.
        announcement = Announcement.objects.get()
        update_announcement(announcement.id, {"title": "Edited", "role_ids": [], "group_ids": []})
        self.assertEqual(list(AnnouncementAudience.objects.values_list("user_id", flat=True)), [emailed.id])
        self.assertEqual(Announcement.objects.get().visibility_scope, "role_based")
        self.assertEqual(seen(not_yet), [])

    def test_nothing_is_posted_before_anyone_is_emailed(self):
        result = SimpleNamespace(supervisors_emailed=set())
        with mock.patch.object(outcome_announcement.results_notify, "results_audience", return_value=result):
            r = self.client.post(_post_url("results-supervisors"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            r.json()["detail"], "No supervisor has been emailed yet. It can be posted once its email has been sent.",
        )


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
        html = f"""
            <h1 style="color:#017151">Title</h1>
            <p style="color:#153226; font-size:16px">
              Dear members of <strong>{NAME}</strong>,
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
            as_announcement(html, "finalists"),
            "<p>Dear finalists,</p>"
            '<div style="border:1px dashed #017151;background-color:#e9f6f1">'
            "<strong>Important:</strong> on <strong>Friday</strong>.</div>"
            "<ul><li>Have one reply to the email we sent you.</li></ul>"
            '<div style="margin:16px 0"><a class="cta-link" href="https://x.org/r"'
            ' style="background-color:#017151;color:#ffffff"'
            ' rel="noopener noreferrer">Register</a></div>',
        )
