"""Finalist selection: the toggle, the candidates table, the finalist list,
and the notify-finalists email flow."""
from decimal import Decimal

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import FinalistFlag, Grade
from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.submissions.models import Submission
from apps.users.models import User

from .fixtures import _GradingFixture


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

    @override_settings(GRADING_FINALIST_EMAIL_ENABLED=True)
    def test_notify_all_emails_unnotified_flags_only(self):
        from django.core import mail

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

    @override_settings(GRADING_FINALIST_EMAIL_ENABLED=True)
    def test_notify_with_group_ids_targets_only_those(self):
        from django.core import mail

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

    @override_settings(GRADING_FINALIST_EMAIL_ENABLED=True)
    def test_notify_flag_marks_notified_when_recipients_exist(self):
        from django.core import mail
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

    def test_notify_off_by_default(self):
        # Env flag OFF → notify=true is honoured as a request but the helper is a no-op.
        self.client.force_authenticate(self.staff)
        r = self.client.post(self.url, {"notify": True}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertFalse(r.json()["notified"])


@override_settings(GRADING_FINALIST_EMAIL_ENABLED=True)
class FinalistNotifyServiceTests(_GradingFixture):
    """The notify helper's skip and failure branches, exercised directly."""

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
        # Non-fatal: the flag survives untouched so a retry can mail later.
        flag.refresh_from_db()
        self.assertFalse(flag.notified)
        self.assertIsNone(flag.notified_at)
