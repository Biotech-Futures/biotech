"""Finalist selection: the toggle, the candidates table, the finalist list,
and the notify-finalists email flow."""
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import FinalistEmailSettings, FinalistFlag, Grade
from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.submissions.models import Submission
from apps.users.models import User

from .fixtures import _GradingFixture


def _days_ahead(days: int):
    """A date ``days`` after Sydney's today, so the tests never go stale."""
    from datetime import timedelta

    from apps.grading.services.finalist_notify import symposium_today

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


class FinalistToggleTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("grading:finalist-toggle", kwargs={"group_id": self.group.id})

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.non_staff)
        r = self.client.post(self.url, {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_upsert_idempotent(self):
        self.client.force_authenticate(self.staff)
        r1 = self.client.post(self.url, {}, format="json")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED, r1.content)
        r2 = self.client.post(self.url, {}, format="json")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(FinalistFlag.objects.filter(group=self.group).count(), 1)

    def test_delete_idempotent(self):
        self.client.force_authenticate(self.staff)
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        r1 = self.client.delete(self.url)
        self.assertEqual(r1.status_code, status.HTTP_204_NO_CONTENT)
        r2 = self.client.delete(self.url)  # already gone
        self.assertEqual(r2.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(FinalistFlag.objects.filter(group=self.group).exists())

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
        url = reverse("grading:finalist-notify")
        r = self.client.post(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["sent"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("member@example.com", mail.outbox[0].to)
        notified_flag = FinalistFlag.objects.get(group=self.group)
        self.assertTrue(notified_flag.notified)
        self.assertIsNotNone(notified_flag.notified_at)

        # Second press: everything already notified (or has no recipients) — no new mail.
        r2 = self.client.post(url)
        self.assertEqual(r2.json()["sent"], 0)
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
        url = reverse("grading:finalist-notify")
        r = self.client.post(url, {"group_ids": [self.group.id]}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["sent"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("member@example.com", mail.outbox[0].to)
        self.assertFalse(FinalistFlag.objects.get(group=other_group).notified)

        # Malformed group_ids is a 400, not a mass send.
        r_bad = self.client.post(url, {"group_ids": "1,2"}, format="json")
        self.assertEqual(r_bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_candidates_totals_markers_and_finalist_state(self):
        Grade.objects.create(
            submission=self.saq_submission, criterion=self.saq_c1,
            mark=Decimal("8.00"), graded_by=self.staff,
        )
        Grade.objects.create(
            submission=self.saq_submission, criterion=self.saq_c2,
            mark=Decimal("4.50"), graded_by=self.staff,
        )
        Grade.objects.create(
            submission=self.poster_submission, criterion=self.poster_c1,
            mark=Decimal("7.00"), graded_by=self.staff,
        )
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        ungraded = Groups.objects.create(group_name="BTF-UNGRADED")

        self.client.force_authenticate(self.staff)
        r = self.client.get(reverse("grading:finalist-candidates"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        body = r.json()
        self.assertEqual([c["code"] for c in body["components"]][:2], ["SAQ", "POSTER"])

        # Only components whose active rubric has criteria appear as columns;
        # REPORT/PROTOTYPE carry no criteria so they are omitted entirely.
        self.assertEqual([c["code"] for c in body["components"]], ["SAQ", "POSTER"])

        rows = {row["group_id"]: row for row in body["rows"]}
        graded = rows[self.group.id]
        self.assertEqual(graded["marks"]["SAQ"], "12.50")
        self.assertEqual(graded["marks"]["POSTER"], "7.00")
        self.assertNotIn("REPORT", graded["marks"])
        self.assertEqual(graded["total"], "19.50")
        # Fixture submits before any deadline exists -> not late, no label.
        self.assertFalse(graded["is_late"])
        self.assertIsNone(graded["late_by"])
        self.assertEqual(graded["markers"], ["Ada Grader"])
        self.assertTrue(graded["is_finalist"])
        # Graded group ranks above the ungraded one.
        self.assertEqual(body["rows"][0]["group_id"], self.group.id)
        self.assertIsNone(rows[ungraded.id]["total"])
        self.assertFalse(rows[ungraded.id]["is_finalist"])
        self.assertTrue(graded["has_submission"])
        self.assertFalse(rows[ungraded.id]["has_submission"])

    def test_candidates_flag_parts_not_marked_completely(self):
        from apps.grading.models import Rubric, RubricCriterion, SubmissionComponent

        # A two-criterion report rubric makes REPORT a column; the fixture
        # team hands in a report with only one of its criteria marked.
        report = SubmissionComponent.objects.get(code="REPORT")
        rubric = Rubric.objects.create(component=report, year=2026, active=True)
        method = RubricCriterion.objects.create(
            rubric=rubric, name="Method", max_mark=Decimal("5"), order=1
        )
        results = RubricCriterion.objects.create(
            rubric=rubric, name="Results", max_mark=Decimal("5"), order=2
        )
        Submission.objects.filter(pk=self.submission.pk).update(submitted_report={
            "storage_key": "2026/01/01/fixture/report.pdf", "name": "report.pdf",
            "mime": "application/pdf", "size": 42,
        })
        for criterion, mark in ((self.saq_c1, "8"), (self.saq_c2, "4"), (method, "3")):
            Grade.objects.create(
                submission=self.submission, criterion=criterion,
                mark=Decimal(mark), graded_by=self.staff,
            )
        empty = Groups.objects.create(group_name="BTF-EMPTY")
        self.client.force_authenticate(self.staff)

        def rows():
            body = self.client.get(reverse("grading:finalist-candidates")).json()
            return {row["group_id"]: row for row in body["rows"]}

        team = rows()[self.group.id]
        # SAQ fully marked; poster not started; report one of two.
        self.assertEqual(team["incomplete"], ["POSTER", "REPORT"])
        self.assertEqual(team["marks"]["REPORT"], "3.00")
        self.assertEqual(rows()[empty.id]["incomplete"], [])

        Grade.objects.create(
            submission=self.submission, criterion=results, mark=Decimal("2"), graded_by=self.staff,
        )
        self.assertEqual(rows()[self.group.id]["incomplete"], ["POSTER"])

    def test_candidates_late_column(self):
        from datetime import timedelta

        from apps.submissions.models import Deadline

        # Deadline 3h12m before the fixture's submit time -> "3h 12m" late.
        Deadline.objects.create(
            closes_at=self.submission.submitted_at - timedelta(hours=3, minutes=12),
            is_active=True,
        )
        Submission.objects.filter(pk=self.submission.pk).update(is_late=True)

        self.client.force_authenticate(self.staff)
        r = self.client.get(reverse("grading:finalist-candidates"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        row = next(x for x in r.json()["rows"] if x["group_id"] == self.group.id)
        self.assertTrue(row["is_late"])
        self.assertEqual(row["late_by"], "3h 12m")

    def test_late_label_drops_minutes_past_a_day(self):
        from datetime import timedelta

        from apps.grading.services.content import late_by_label

        # Day-scale lateness drops the minutes; smaller scales keep them.
        self.assertEqual(late_by_label(timedelta(days=5, hours=1, minutes=58)), "5d 1h")
        self.assertEqual(late_by_label(timedelta(hours=22, minutes=54)), "22h 54m")
        self.assertEqual(late_by_label(timedelta(minutes=45)), "45m")

    def test_notify_all_denied_for_non_staff(self):
        self.client.force_authenticate(self.non_staff)
        r = self.client.post(reverse("grading:finalist-notify"))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_returns_flagged_groups(self):
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        self.client.force_authenticate(self.staff)
        r = self.client.get(reverse("grading:finalist-list"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        rows = r.json()["finalists"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["group_id"], self.group.id)

    def test_list_counts_each_teams_students(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        User = get_user_model()
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        for n, (role, left) in enumerate((("student", None), ("student", None), ("student", timezone.now()), ("mentor", None))):
            member = User.objects.create_user(email=f"m{n}@example.com", password="pw12345!")
            GroupMembership.objects.create(
                group=self.group, user=member, membership_role=role,
                joined_at=timezone.now() - timezone.timedelta(days=30), left_at=left,
            )
        self.client.force_authenticate(self.staff)
        rows = self.client.get(reverse("grading:finalist-list")).json()["finalists"]
        # Two current students; the one who left and the mentor don't count.
        self.assertEqual(rows[0]["students"], 2)

    def test_notify_flag_marks_notified_when_recipients_exist(self):
        from django.core import mail

        _set_email_details()
        # Fixture staff user is is_staff=True; add as a member so they get the mail.
        GroupMembership.objects.create(
            group=self.group, user=self.staff,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        self.client.force_authenticate(self.staff)
        r = self.client.post(self.url, {"notify": True}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self.assertTrue(r.json()["notified"])
        self.assertGreaterEqual(len(mail.outbox), 1)

    def test_notify_without_email_details_sends_nothing(self):
        # notify=true is honoured as a request, but with no email details set
        # the helper is a no-op: the team is flagged, not emailed.
        self.client.force_authenticate(self.staff)
        r = self.client.post(self.url, {"notify": True}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertFalse(r.json()["notified"])


class FinalistNotifyServiceTests(_GradingFixture):
    """The notify helper's skip and failure branches, exercised directly."""

    def setUp(self):
        _set_email_details()

    def test_an_already_notified_flag_is_not_remailed(self):
        from django.core import mail

        from apps.grading.services.finalist_notify import notify_finalist

        flag = FinalistFlag.objects.create(
            group=self.group, flagged_by=self.staff, notified=True,
        )
        self.assertFalse(notify_finalist(flag))
        self.assertEqual(len(mail.outbox), 0)

    def test_a_group_with_no_members_is_skipped(self):
        from django.core import mail

        from apps.grading.services.finalist_notify import notify_finalist

        # The fixture group has a submission but no memberships — nobody to mail.
        flag = FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        self.assertFalse(notify_finalist(flag))
        self.assertEqual(len(mail.outbox), 0)
        flag.refresh_from_db()
        self.assertFalse(flag.notified)

    def test_a_send_failure_leaves_the_flag_unnotified(self):
        from unittest.mock import patch

        from apps.grading.services.finalist_notify import notify_finalist

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

    def test_details_start_empty_with_the_usual_registration_link(self):
        body = self.client.get(reverse("grading:finalist-email")).json()
        self.assertEqual(
            (body["symposium_date"], body["confirm_by"], body["slides_due"]), (None, None, None)
        )
        self.assertEqual(
            body["registration_url"], "https://events.humanitix.com/biotech-futures-symposium"
        )
        self.assertFalse(body["complete"])

    def test_details_save_and_report_complete(self):
        symposium = _days_ahead(30)
        r = self.client.patch(reverse("grading:finalist-email"), {
            "symposium_date": str(symposium), "confirm_by": str(_days_ahead(10)),
            "slides_due": str(_days_ahead(20)), "registration_url": "https://events.example.com/s",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertTrue(r.json()["complete"])
        self.assertEqual(r.json()["dates_in_past"], [])
        self.assertEqual(FinalistEmailSettings.load().symposium_date, symposium)

    def test_details_refuse_a_link_that_is_not_a_web_address(self):
        r = self.client.patch(
            reverse("grading:finalist-email"), {"registration_url": "not a link"}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_details_are_for_graders_only(self):
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(
            self.client.get(reverse("grading:finalist-email")).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_sending_is_refused_until_every_detail_is_set(self):
        from django.core import mail

        self._member("stu@example.com", "student")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        r = self.client.post(reverse("grading:finalist-notify"))
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

        r = self.client.post(reverse("grading:finalist-notify"))
        self.assertEqual(r.json()["sent"], 1)
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

        from apps.grading.services.finalist_notify import notify_finalist

        _set_email_details()
        self._member("stu@example.com", "student")
        flag = FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("down")):
            self.assertFalse(notify_finalist(flag, actor=self.staff))
        flag.refresh_from_db()
        self.assertFalse(flag.notified)
        self.assertIsNone(flag.notified_at)
        self.assertIsNone(flag.notified_by)

    def test_preview_shows_unsaved_details_and_the_logo_inline(self):
        from django.core import mail

        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        symposium = _days_ahead(33)
        r = self.client.post(reverse("grading:finalist-email-preview"), {
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
        r = self.client.patch(reverse("grading:finalist-email"), {
            "symposium_date": str(_days_ahead(-1)), "slides_due": str(_days_ahead(0)),
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        fields = r.json()["fields"]
        self.assertEqual(fields["symposium_date"], ["Can't be before today."])
        self.assertNotIn("slides_due", fields)  # today itself is fine
        self.assertIsNone(FinalistEmailSettings.load().symposium_date)

    def test_the_page_is_told_today_and_which_saved_dates_have_passed(self):
        details = _set_email_details()
        FinalistEmailSettings.objects.filter(pk=details.pk).update(confirm_by=_days_ahead(-5))
        body = self.client.get(reverse("grading:finalist-email")).json()
        self.assertEqual(body["today"], str(_days_ahead(0)))
        self.assertEqual(body["dates_in_past"], ["confirm_by"])

    def test_a_passed_date_can_stay_while_other_details_change(self):
        details = _set_email_details()
        passed = _days_ahead(-200)  # last year's, say
        FinalistEmailSettings.objects.filter(pk=details.pk).update(confirm_by=passed)
        r = self.client.patch(reverse("grading:finalist-email"), {
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
        r = self.client.post(reverse("grading:finalist-notify"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("can't be before today", r.json()["detail"])
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(FinalistFlag.objects.get(group=self.group).notified)
