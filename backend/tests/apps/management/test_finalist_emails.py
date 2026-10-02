"""The finalist email: its details, its preview, and Notify Finalists,
which emails every finalist team not yet told."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import FinalistFlag
from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.management.models import FinalistEmailSettings
from apps.users.models import User

from tests.apps.grading.fixtures import _GradingFixture, just_closed


def _days_ahead(days: int):
    """A date ``days`` after Sydney's today, so the tests never go stale."""
    from datetime import timedelta

    from apps.management.services.finalist_notify import symposium_today

    return symposium_today() + timedelta(days=days)


def _long(day) -> str:
    """How the email writes a date: "Friday, 23 October 2026"."""
    return f"{day:%A}, {day.day} {day:%B %Y}"


def _set_email_details():
    """Fill in everything the finalist email needs, so sends can go out."""
    details = FinalistEmailSettings.load()
    details.symposium_date = _days_ahead(30)
    details.confirm_by = _days_ahead(10)
    details.slides_due = _days_ahead(20)
    details.registration_url = "https://events.example.com/symposium"
    details.save()
    return details


class FinalistNotifyAllTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()

    def test_notify_all_emails_unnotified_flags_only(self):
        from django.core import mail

        _set_email_details()
        member = User.objects.create_user(
            email="member@example.com", first_name="Mem", last_name="Ber", password="pw12345!",
        )
        GroupMembership.objects.create(
            group=self.group, user=member, membership_role="student",
        )
        already = Groups.objects.create(group_name="BTF-TEST-2")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        FinalistFlag.objects.create(group=already, flagged_by=self.staff, notified=True)

        self.client.force_authenticate(self.staff)
        url = reverse("management:finalist-notify")
        r = self.client.post(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        # The run is done by the reply under test settings: one person emailed.
        self.assertFalse(r.json()["sending"])
        self.assertEqual((r.json()["run"]["due"], r.json()["run"]["emailed"]), (1, 1))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("member@example.com", mail.outbox[0].to)
        notified_flag = FinalistFlag.objects.get(group=self.group)
        self.assertTrue(notified_flag.notified)
        self.assertIsNotNone(notified_flag.notified_at)

        # Second press: everything already notified (or has no recipients) — no new mail.
        r2 = self.client.post(url)
        self.assertEqual(r2.json()["run"]["due"], 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_notify_with_group_ids_targets_only_those(self):
        from django.core import mail

        _set_email_details()
        member = User.objects.create_user(
            email="member@example.com", first_name="Mem", last_name="Ber", password="pw12345!",
        )
        GroupMembership.objects.create(group=self.group, user=member, membership_role="student")
        other_group = Groups.objects.create(group_name="BTF-TEST-3")
        other_member = User.objects.create_user(
            email="other@example.com", first_name="Oth", last_name="Er", password="pw12345!",
        )
        GroupMembership.objects.create(group=other_group, user=other_member, membership_role="student")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        FinalistFlag.objects.create(group=other_group, flagged_by=self.staff)

        self.client.force_authenticate(self.staff)
        url = reverse("management:finalist-notify")
        r = self.client.post(url, {"group_ids": [self.group.id]}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["run"]["emailed"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("member@example.com", mail.outbox[0].to)
        self.assertFalse(FinalistFlag.objects.get(group=other_group).notified)

        # Malformed group_ids is a 400, not a mass send.
        r_bad = self.client.post(url, {"group_ids": "1,2"}, format="json")
        self.assertEqual(r_bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_notify_all_denied_for_non_staff(self):
        self.client.force_authenticate(self.non_staff)
        r = self.client.post(reverse("management:finalist-notify"))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class FinalistNotifyServiceTests(_GradingFixture):
    """The notify helper's skip and failure branches, exercised directly."""

    def setUp(self):
        _set_email_details()

    def test_an_already_notified_flag_is_not_remailed(self):
        from django.core import mail

        from apps.management.services.finalist_notify import notify_finalist

        flag = FinalistFlag.objects.create(
            group=self.group, flagged_by=self.staff, notified=True,
        )
        self.assertFalse(notify_finalist(flag))
        self.assertEqual(len(mail.outbox), 0)

    def test_a_group_with_no_members_is_skipped(self):
        from django.core import mail

        from apps.management.services.finalist_notify import notify_finalist

        # The fixture group has a submission but no memberships — nobody to mail.
        flag = FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        self.assertFalse(notify_finalist(flag))
        self.assertEqual(len(mail.outbox), 0)
        flag.refresh_from_db()
        self.assertFalse(flag.notified)

    def test_a_send_failure_leaves_the_flag_unnotified(self):
        from unittest.mock import patch

        from apps.management.services.finalist_notify import notify_finalist

        member = User.objects.create_user(
            email="member@example.com", first_name="Mem", last_name="Ber", password="pw12345!",
        )
        GroupMembership.objects.create(group=self.group, user=member, membership_role="student")
        flag = FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)

        # Finalist emails go through the shared system email path now, so the
        # send seam is the message itself rather than a send_mail import.
        with patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=Exception("relay down"),
        ):
            self.assertFalse(notify_finalist(flag))
        # Non-fatal: the flag stays not notified so a retry can mail later.
        flag.refresh_from_db()
        self.assertFalse(flag.notified)
        self.assertIsNone(flag.notified_at)


class FinalistEmailTests(_GradingFixture):
    """The email details, the email itself, and its preview."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def _member(self, email, role):
        user = User.objects.create_user(
            email=email, first_name=email.split("@")[0], last_name="X", password="pw12345!",
        )
        GroupMembership.objects.create(group=self.group, user=user, membership_role=role)
        return user

    def test_details_start_empty(self):
        # The registration link too: last year's must never go out unnoticed.
        body = self.client.get(reverse("management:finalist-email")).json()
        self.assertEqual(
            (body["symposium_date"], body["confirm_by"], body["slides_due"], body["registration_url"]),
            (None, None, None, ""),
        )
        self.assertFalse(body["complete"])

    def test_details_save_and_report_complete(self):
        symposium = _days_ahead(30)
        r = self.client.patch(reverse("management:finalist-email"), {
            "symposium_date": str(symposium), "confirm_by": str(_days_ahead(10)),
            "slides_due": str(_days_ahead(20)), "registration_url": "https://events.example.com/s",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertTrue(r.json()["complete"])
        self.assertEqual(r.json()["dates_in_past"], [])
        self.assertEqual(FinalistEmailSettings.load().symposium_date, symposium)

    def test_details_refuse_a_link_that_is_not_a_web_address(self):
        r = self.client.patch(
            reverse("management:finalist-email"), {"registration_url": "not a link"}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_details_are_for_graders_only(self):
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(
            self.client.get(reverse("management:finalist-email")).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_sending_is_refused_until_every_detail_is_set(self):
        from django.core import mail

        self._member("stu@example.com", "student")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        r = self.client.post(reverse("management:finalist-notify"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Symposium date", r.json()["detail"])
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(FinalistFlag.objects.get(group=self.group).notified)

    def test_each_member_gets_their_own_copy_of_the_clients_email(self):
        from django.core import mail

        details = _set_email_details()
        for email, role in (
            ("stu@example.com", "student"),
            ("men@example.com", "mentor"),
            ("sup@example.com", "supervisor"),
        ):
            self._member(email, role)
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)

        r = self.client.post(reverse("management:finalist-notify"))
        # The people it went to, for the page's progress.
        self.assertEqual((r.json()["run"]["due"], r.json()["run"]["emailed"]), (3, 3))
        self.assertEqual(
            sorted(m.to[0] for m in mail.outbox),
            ["men@example.com", "stu@example.com", "sup@example.com"],
        )
        message = mail.outbox[0]
        self.assertEqual(len(message.to), 1)  # nobody sees another member's address
        self.assertEqual(message.subject, "Congratulations \u2013 You\u2019re a BIOTech Futures Finalist!")
        self.assertEqual(message.reply_to, ["support@biotechfutures.org"])
        html = message.alternatives[0][0]
        for text in (
            "Dear members of <strong>BTF-TEST-1</strong>",
            _long(details.symposium_date),
            _long(details.confirm_by),
            _long(details.slides_due),
            'href="https://events.example.com/symposium"',
            "cid:btf-logo",
        ):
            self.assertIn(text, html)
        self.assertIn(f"Please confirm by {_long(details.confirm_by)}.", message.body)
        flag = FinalistFlag.objects.get(group=self.group)
        self.assertTrue(flag.notified)
        self.assertEqual(flag.notified_by, self.staff)

    def test_a_team_whose_every_email_fails_stays_not_notified(self):
        from unittest.mock import patch

        from apps.management.services.finalist_notify import notify_finalist

        _set_email_details()
        self._member("stu@example.com", "student")
        flag = FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("down")):
            self.assertFalse(notify_finalist(flag, actor=self.staff))
        flag.refresh_from_db()
        self.assertFalse(flag.notified)
        self.assertIsNone(flag.notified_at)
        self.assertIsNone(flag.notified_by)

    def test_a_run_names_the_member_it_could_not_reach(self):
        from unittest import mock

        from django.core import mail

        _set_email_details()
        self._member("stu@example.com", "student")
        self._member("men@example.com", "mentor")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        real_send = mail.EmailMultiAlternatives.send

        def fail_for_stu(message, *args, **kwargs):
            if message.to == ["stu@example.com"]:
                raise OSError("rejected")
            return real_send(message, *args, **kwargs)

        with mock.patch("django.core.mail.EmailMultiAlternatives.send", autospec=True, side_effect=fail_for_stu), \
                self.assertLogs("apps.management.services.finalist_notify", level="ERROR"):
            run = self.client.post(reverse("management:finalist-notify")).json()["run"]
        self.assertEqual(
            (run["due"], run["emailed"], run["failed"], run["missed"]),
            (2, 1, 1, [{"who": f"({self.group.group_name}) stu X", "reason": "lost the mail server connection"}]),
        )
        self.assertFalse(FinalistFlag.objects.get(group=self.group).notified)
        # The mentor it reached counts as emailed; the student doesn't.
        counts = self.client.get(reverse("management:finalist-email")).json()["counts"]
        self.assertEqual(
            (counts["students"]["emailed"], counts["mentors"], counts["supervisors"]["emailed"]),
            (0, {"total": 1, "emailed": 1, "times": {"total": 1, "emailed": 1}}, 0),
        )

        # Pressing again emails only the student it missed, and the team is done.
        mail.outbox = []
        run = self.client.post(reverse("management:finalist-notify")).json()["run"]
        self.assertEqual([m.to for m in mail.outbox], [["stu@example.com"]])
        self.assertEqual((run["due"], run["emailed"], run["failed"]), (1, 1, 0))
        self.assertTrue(FinalistFlag.objects.get(group=self.group).notified)

    def test_newly_added_and_retry_missed_each_email_only_their_own(self):
        from unittest import mock

        from django.core import mail

        _set_email_details()
        self._member("stu@example.com", "student")
        self._member("men@example.com", "mentor")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        real_send = mail.EmailMultiAlternatives.send

        def fail_for_stu(message, *args, **kwargs):
            if message.to == ["stu@example.com"]:
                raise OSError("rejected")
            return real_send(message, *args, **kwargs)

        with mock.patch("django.core.mail.EmailMultiAlternatives.send", autospec=True, side_effect=fail_for_stu), \
                self.assertLogs("apps.management.services.finalist_notify", level="ERROR"):
            self.client.post(reverse("management:finalist-notify"))
        # A team flagged after that send.
        late = Groups.objects.create(group_name="BTF-LATE")
        newbie = User.objects.create_user(email="new@example.com", first_name="New", last_name="X", password="pw12345!")
        GroupMembership.objects.create(group=late, user=newbie, membership_role="student")
        FinalistFlag.objects.create(group=late, flagged_by=self.staff)

        waiting = lambda: self.client.get(reverse("management:finalist-email")).json()["waiting"]  # noqa: E731
        self.assertEqual(waiting(), {
            "new": {"teams": 1, "people": 1, "groups": ["BTF-LATE"]},
            "missed": {"teams": 1, "people": 1, "groups": [self.group.group_name]},
        })

        # Retry emails only the student it missed, not the new team.
        mail.outbox = []
        self.client.post(reverse("management:finalist-notify"), {"which": "missed"}, format="json")
        self.assertEqual([m.to for m in mail.outbox], [["stu@example.com"]])
        self.assertTrue(FinalistFlag.objects.get(group=self.group).notified)
        self.assertFalse(FinalistFlag.objects.get(group=late).notified)

        # Newly added emails only the new team.
        mail.outbox = []
        self.client.post(reverse("management:finalist-notify"), {"which": "new"}, format="json")
        self.assertEqual([m.to for m in mail.outbox], [["new@example.com"]])
        self.assertEqual(waiting(), {
            "new": {"teams": 0, "people": 0, "groups": []}, "missed": {"teams": 0, "people": 0, "groups": []},
        })

    def test_a_team_the_last_send_missed_entirely_is_one_to_retry(self):
        from django.utils import timezone

        from apps.management.models import EmailSendRun

        self._member("stu@example.com", "student")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        # Nobody on it got the email, but the last send named them.
        EmailSendRun.objects.create(
            key="finalist_notification", started_at=timezone.now(), missed=[f"({self.group.group_name}) stu X"],
        )
        waiting = self.client.get(reverse("management:finalist-email")).json()["waiting"]
        self.assertEqual(waiting, {
            "new": {"teams": 0, "people": 0, "groups": []},
            "missed": {"teams": 1, "people": 1, "groups": [self.group.group_name]},
        })

    def test_send_refuses_an_unknown_which(self):
        _set_email_details()
        r = self.client.post(reverse("management:finalist-notify"), {"which": "everyone"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_preview_shows_unsaved_details_and_the_logo_inline(self):
        from django.core import mail

        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        symposium = _days_ahead(33)
        r = self.client.post(reverse("management:finalist-email-preview"), {
            "symposium_date": str(symposium), "registration_url": "https://events.example.com/p",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        body = r.json()
        self.assertEqual(body["group_name"], "BTF-TEST-1")
        self.assertIn(_long(symposium), body["html"])
        self.assertIn("[not set]", body["html"])  # confirm-by and slides due are still blank
        self.assertIn('src="data:image/png;base64,', body["html"])
        self.assertNotIn("cid:", body["html"])
        # Previewing saves nothing and sends nothing.
        self.assertIsNone(FinalistEmailSettings.load().symposium_date)
        self.assertEqual(len(mail.outbox), 0)

    def test_a_date_before_today_is_refused(self):
        r = self.client.patch(reverse("management:finalist-email"), {
            "symposium_date": str(_days_ahead(-1)), "slides_due": str(_days_ahead(0)),
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        fields = r.json()["fields"]
        self.assertEqual(fields["symposium_date"], ["Can't be before today."])
        self.assertNotIn("slides_due", fields)  # today itself is fine
        self.assertIsNone(FinalistEmailSettings.load().symposium_date)

    def test_sending_waits_for_submissions_to_close(self):
        from datetime import timedelta

        from django.core import mail
        from django.utils import timezone

        from apps.submissions.models import Deadline, GroupExtension

        _set_email_details()
        self._member("stu@example.com", "student")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        deadline = Deadline.objects.create(closes_at=just_closed(hours=1), grace_hours=3)
        body = self.client.get(reverse("management:finalist-email")).json()
        self.assertTrue(body["submissions_open"].startswith("Submissions are open until "), body)
        r = self.client.post(reverse("management:finalist-notify"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.json()["detail"], body["submissions_open"])

        # Then the last extension, grace hours included.
        Deadline.objects.filter(pk=deadline.pk).update(grace_hours=0)
        GroupExtension.objects.create(
            group=self.group, extended_until=timezone.now() - timedelta(hours=1), grace_hours=2,
        )
        r = self.client.post(reverse("management:finalist-notify"))
        self.assertTrue(r.json()["detail"].startswith("A team's extension is open until "), r.json())
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(FinalistFlag.objects.get(group=self.group).notified)

        # Flagging a team still works; only its email waits.
        other = Groups.objects.create(group_name="Other")
        r = self.client.post(
            reverse("grading:finalist-toggle", kwargs={"group_id": other.id}), {"notify": True}, format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self.assertFalse(r.json()["notified"])
        self.assertTrue(FinalistFlag.objects.filter(group=other).exists())

    def test_a_send_pressed_while_another_runs_is_queued_until_it_finishes(self):
        from datetime import timedelta

        from django.core import mail
        from django.utils import timezone

        from apps.management.models import EmailSendRun

        _set_email_details()
        self._member("stu@example.com", "student")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        EmailSendRun.objects.create(
            key="finalist_notification", held_until=timezone.now() + timedelta(minutes=4), started_at=timezone.now(),
        )
        self.assertTrue(self.client.get(reverse("management:finalist-email")).json()["sending"])
        r = self.client.post(reverse("management:finalist-notify"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["queued"], 1)
        self.assertEqual(len(mail.outbox), 0)

        # Once that run finishes, the page's next check sends it.
        EmailSendRun.objects.filter(key="finalist_notification").update(held_until=None, finished_at=timezone.now())
        body = self.client.get(reverse("management:finalist-email")).json()
        self.assertEqual((body["queued"], body["run"]["emailed"]), (0, 1))
        self.assertEqual([m.to for m in mail.outbox], [["stu@example.com"]])
        self.assertFalse(self.client.get(reverse("management:finalist-email")).json()["sending"])

    def test_the_page_is_told_today_and_which_saved_dates_have_passed(self):
        details = _set_email_details()
        FinalistEmailSettings.objects.filter(pk=details.pk).update(confirm_by=_days_ahead(-5))
        body = self.client.get(reverse("management:finalist-email")).json()
        self.assertEqual(body["today"], str(_days_ahead(0)))
        self.assertEqual(body["dates_in_past"], ["confirm_by"])

    def test_a_passed_date_can_stay_while_other_details_change(self):
        details = _set_email_details()
        passed = _days_ahead(-200)  # last year's, say
        FinalistEmailSettings.objects.filter(pk=details.pk).update(confirm_by=passed)
        r = self.client.patch(reverse("management:finalist-email"), {
            "confirm_by": str(passed), "registration_url": "https://events.example.com/new",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["registration_url"], "https://events.example.com/new")

    def test_sending_is_refused_while_a_saved_date_has_passed(self):
        from django.core import mail

        details = _set_email_details()
        FinalistEmailSettings.objects.filter(pk=details.pk).update(symposium_date=_days_ahead(-1))
        self._member("stu@example.com", "student")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        r = self.client.post(reverse("management:finalist-notify"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("can't be before today", r.json()["detail"])
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(FinalistFlag.objects.get(group=self.group).notified)

    def test_details_count_each_teams_students_mentors_and_supervisors(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        User = get_user_model()
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        members = (
            ("student", None), ("student", None), ("student", timezone.now()),
            ("mentor", None), ("supervisor", None), ("supervisor", None),
        )
        for n, (role, left) in enumerate(members):
            member = User.objects.create_user(email=f"m{n}@example.com", password="pw12345!")
            GroupMembership.objects.create(
                group=self.group, user=member, membership_role=role,
                joined_at=timezone.now() - timezone.timedelta(days=30), left_at=left,
            )
        # People and emails, by role: current members only, so not the
        # student who left; nobody's emailed until the team is notified.
        counts = self.client.get(reverse("management:finalist-email")).json()["counts"]
        self.assertEqual(counts["students"], {"total": 2, "emailed": 0, "times": {"total": 2, "emailed": 0}})
        self.assertEqual(counts["mentors"], {"total": 1, "emailed": 0, "times": {"total": 1, "emailed": 0}})
        self.assertEqual(counts["supervisors"], {"total": 2, "emailed": 0, "times": {"total": 2, "emailed": 0}})

    def test_a_mentor_on_two_finalist_teams_counts_once_with_two_emails(self):
        from django.contrib.auth import get_user_model

        mentor = get_user_model().objects.create_user(email="mo@example.com", password="pw12345!")
        other = Groups.objects.create(group_name="BTF-OTHER")
        for team, notified in ((self.group, True), (other, False)):
            FinalistFlag.objects.create(group=team, flagged_by=self.staff, notified=notified)
            GroupMembership.objects.create(group=team, user=mentor, membership_role="mentor")
        counts = self.client.get(reverse("management:finalist-email")).json()["counts"]
        # One mentor, emailed with the notified team; one of their two emails.
        self.assertEqual(counts["mentors"], {"total": 1, "emailed": 1, "times": {"total": 2, "emailed": 1}})
