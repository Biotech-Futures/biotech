"""The Symposium emails from the Email Nonfinalist tab, to teams that
submitted but weren't picked and to teams that didn't submit: who gets them,
the client's wording with the Symposium details from Notify Finalists,
preview, and sending in batches."""
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import FinalistEmailSettings, FinalistFlag, NonFinalistEmail, NonSubmissionEmail
from apps.grading.services.finalist_notify import symposium_today
from apps.grading.services.symposium_emails import NONFINALIST, send_batch
from apps.groups.models import GroupMembership, Groups
from apps.services.models import SystemEmailTemplate
from apps.submissions.models import Submission
from apps.users.models import User

from .fixtures import _GradingFixture

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
SEND = "grading:nonfinalist-email-send"
NS_SEND = "grading:nonsubmission-email-send"


def _member(email, group, role="student", left_at=None):
    user = User.objects.create_user(email=email, first_name="Mem", last_name=email.split("@")[0], password="pw12345!")
    GroupMembership.objects.create(
        user=user, group=group, membership_role=role,
        joined_at=timezone.now() - timedelta(days=30), left_at=left_at,
    )
    return user


def _submitted_team(name, staff):
    team = Groups.objects.create(group_name=name)
    submission = Submission.objects.create(group=team, answers={"q_answers": "Answers."})
    submission.snapshot(staff)
    submission.save()
    return team


@override_settings(EMAIL_BACKEND=LOCMEM)
class NonFinalistEmailTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

        # The fixture's submitted team wasn't picked: two students, a mentor, a
        # supervisor and a student who left. Everyone current gets the email.
        _member("amy@example.com", self.group)
        _member("ben@example.com", self.group)
        _member("mo@example.com", self.group, role="mentor")
        _member("sue@example.com", self.group, role="supervisor")
        _member("gone@example.com", self.group, left_at=timezone.now())

        # A finalist team and a team that never submitted don't get it.
        finalist = _submitted_team("Picked", self.staff)
        _member("fin@example.com", finalist)
        FinalistFlag.objects.create(group=finalist, flagged_by=self.staff)
        no_entry = Groups.objects.create(group_name="No Entry")
        _member("none@example.com", no_entry)

        details = FinalistEmailSettings.load()
        details.symposium_date = symposium_today() + timedelta(days=30)
        details.registration_url = "https://events.example.com/symposium"
        details.save()

    def _send_all(self):
        cursor, results = None, []
        while True:
            r = self.client.post(reverse(SEND), {"cursor": cursor}, format="json")
            self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
            results.append(r.json())
            cursor = r.json()["cursor"]
            if r.json()["done"]:
                return results

    def _recipients(self):
        return sorted(m.to[0] for m in mail.outbox)

    def test_every_current_member_of_a_team_not_picked_gets_it(self):
        results = self._send_all()
        self.assertEqual(
            self._recipients(),
            ["amy@example.com", "ben@example.com", "mo@example.com", "sue@example.com"],
        )
        message = mail.outbox[0]
        text = " ".join(message.body.split())
        self.assertEqual(message.subject, "Thank you for your submission – Invitation to the Symposium")
        self.assertIn(f"Dear members of {self.group.group_name},", text)
        self.assertIn("your team was not selected as a finalist", text)
        day = FinalistEmailSettings.load().symposium_date
        self.assertIn(f"Symposium on {day:%A}, {day.day} {day:%B %Y}", text)
        self.assertIn("https://events.example.com/symposium", text)
        self.assertEqual(message.reply_to, ["support@biotechfutures.org"])

        self.assertEqual(results[-1]["emailed"], 4)
        self.assertEqual(results[-1]["teams"], {"total": 1, "emailed": 1})
        # The count is of students; mentors and supervisors get it too.
        self.assertEqual(results[-1]["students"], {"total": 2, "emailed": 2, "times": {"total": 2, "emailed": 2}})
        self.assertTrue(NonFinalistEmail.objects.filter(group=self.group).exists())

    def test_a_second_send_emails_nobody_again(self):
        self._send_all()
        mail.outbox = []
        self.assertTrue(self._send_all()[-1]["done"])
        self.assertEqual(mail.outbox, [])

    def test_batches_move_on_and_report_progress(self):
        for n in range(6):
            _member(f"extra{n}@example.com", _submitted_team(f"Extra {n}", self.staff))
        first = send_batch(NONFINALIST, self.staff, None, limit=5)
        self.assertEqual((first["emailed"], first["done"]), (8, False))  # the fixture team has four members
        second = send_batch(NONFINALIST, self.staff, first["cursor"], limit=5)
        self.assertEqual((second["emailed"], second["done"]), (2, True))
        self.assertEqual(second["teams"], {"total": 7, "emailed": 7})

    def test_a_team_whose_member_misses_it_stays_pending(self):
        real_send = mail.EmailMultiAlternatives.send

        def fail_for_ben(message, *args, **kwargs):
            if message.to == ["ben@example.com"]:
                raise OSError("rejected")
            return real_send(message, *args, **kwargs)

        with mock.patch("django.core.mail.EmailMultiAlternatives.send", autospec=True, side_effect=fail_for_ben), \
                self.assertLogs("apps.grading.services.symposium_emails", level="ERROR"):
            results = self._send_all()
        self.assertEqual(sum(r["failed"] for r in results), 1)
        self.assertEqual(results[-1]["students"], {"total": 2, "emailed": 0, "times": {"total": 2, "emailed": 0}})
        self.assertFalse(NonFinalistEmail.objects.filter(group=self.group).exists())

        # The next press reaches the team again.
        self._send_all()
        self.assertTrue(NonFinalistEmail.objects.filter(group=self.group).exists())

    def test_sending_waits_for_the_symposium_details_on_notify_finalists(self):
        FinalistEmailSettings.objects.update(symposium_date=None)
        r = self.client.post(reverse(SEND), {}, format="json")
        self.assertEqual(
            r.json()["detail"], "Set the Symposium date and registration link on Notify Finalists before sending.",
        )
        self.assertEqual(self.client.get(reverse("grading:nonfinalist-email")).json()["blocked"], r.json()["detail"])

        FinalistEmailSettings.objects.update(symposium_date=symposium_today() - timedelta(days=1))
        r = self.client.post(reverse(SEND), {}, format="json")
        self.assertEqual(
            r.json()["detail"], "The Symposium date on Notify Finalists is before today. Update it before sending.",
        )
        self.assertEqual(mail.outbox, [])

    def test_a_switched_off_email_is_refused(self):
        SystemEmailTemplate.objects.create(key="nonfinalist_invitation", is_enabled=False)
        r = self.client.post(reverse(SEND), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.json()["detail"], "Non-finalist invitation is switched off on System Emails.")

    def test_the_tab_shows_who_it_is_for(self):
        r = self.client.get(reverse("grading:nonfinalist-email"))
        # The student who left isn't counted.
        self.assertEqual(r.json(), {
            "teams": {"total": 1, "emailed": 0},
            "students": {"total": 2, "emailed": 0, "times": {"total": 2, "emailed": 0}},
            "mentors": {"total": 1, "emailed": 0, "times": {"total": 1, "emailed": 0}},
            "supervisors": {"total": 1, "emailed": 0, "times": {"total": 1, "emailed": 0}},
            "blocked": "",
        })

    def test_preview_is_addressed_to_the_first_team_due(self):
        r = self.client.post(reverse("grading:nonfinalist-email-preview"), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["to"], self.group.group_name)
        self.assertIn('href="https://events.example.com/symposium"', r.json()["html"])
        self.assertIn("Register to Attend (In-Person)", r.json()["html"])
        self.assertEqual(mail.outbox, [])

    def test_graders_only(self):
        self.client.force_authenticate(self.non_staff)
        for name in ("grading:nonfinalist-email", "grading:nonsubmission-email"):
            self.assertEqual(self.client.get(reverse(name)).status_code, status.HTTP_403_FORBIDDEN)
        for name in ("grading:nonfinalist-email-preview", SEND, "grading:nonsubmission-email-preview", NS_SEND):
            self.assertEqual(self.client.post(reverse(name), {}, format="json").status_code, status.HTTP_403_FORBIDDEN)


@override_settings(EMAIL_BACKEND=LOCMEM)
class NonSubmissionEmailTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

        # Teams that didn't submit: one never started, one only saved a draft.
        self.no_entry = Groups.objects.create(group_name="No Entry")
        _member("nia@example.com", self.no_entry)
        _member("mo@example.com", self.no_entry, role="mentor")
        _member("sue@example.com", self.no_entry, role="supervisor")
        self.draft = Groups.objects.create(group_name="Draft Only")
        Submission.objects.create(group=self.draft, answers={"q_answers": "Not sent."})
        _member("dee@example.com", self.draft)

        # Not due it: the fixture team submitted; a group of just a mentor
        # isn't a team that entered; a group with nobody has no one to email.
        _member("amy@example.com", self.group)
        mentor_only = Groups.objects.create(group_name="Mentor Only")
        _member("solo@example.com", mentor_only, role="mentor")
        Groups.objects.create(group_name="Nobody")

        details = FinalistEmailSettings.load()
        details.symposium_date = symposium_today() + timedelta(days=30)
        details.registration_url = "https://events.example.com/symposium"
        details.save()

    def _send_all(self):
        cursor, results = None, []
        while True:
            r = self.client.post(reverse(NS_SEND), {"cursor": cursor}, format="json")
            self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
            results.append(r.json())
            cursor = r.json()["cursor"]
            if r.json()["done"]:
                return results

    def test_the_section_counts_teams_that_did_not_submit(self):
        r = self.client.get(reverse("grading:nonsubmission-email"))
        # Not the mentor of the group that never entered.
        self.assertEqual(r.json(), {
            "teams": {"total": 2, "emailed": 0},
            "students": {"total": 2, "emailed": 0, "times": {"total": 2, "emailed": 0}},
            "mentors": {"total": 1, "emailed": 0, "times": {"total": 1, "emailed": 0}},
            "supervisors": {"total": 1, "emailed": 0, "times": {"total": 1, "emailed": 0}},
            "blocked": "",
        })

    def test_everyone_counts_as_emailed_once_their_team_is(self):
        self._send_all()
        r = self.client.get(reverse("grading:nonsubmission-email")).json()
        self.assertEqual(
            (r["students"], r["mentors"], r["supervisors"]),
            ({"total": 2, "emailed": 2, "times": {"total": 2, "emailed": 2}}, {"total": 1, "emailed": 1, "times": {"total": 1, "emailed": 1}}, {"total": 1, "emailed": 1, "times": {"total": 1, "emailed": 1}}),
        )

    def test_a_mentor_on_two_teams_is_one_person_emailed_twice(self):
        # The team that saved a draft shares its supervisor with the other.
        sue = GroupMembership.objects.get(user__email="sue@example.com").user
        GroupMembership.objects.create(group=self.draft, user=sue, membership_role="supervisor")
        r = self.client.get(reverse("grading:nonsubmission-email")).json()
        self.assertEqual(r["supervisors"], {"total": 1, "emailed": 0, "times": {"total": 2, "emailed": 0}})
        self._send_all()
        r = self.client.get(reverse("grading:nonsubmission-email")).json()
        self.assertEqual(r["supervisors"], {"total": 1, "emailed": 1, "times": {"total": 2, "emailed": 2}})

    def test_every_current_member_of_a_team_that_did_not_submit_gets_it(self):
        results = self._send_all()
        self.assertEqual(
            sorted(m.to[0] for m in mail.outbox),
            ["dee@example.com", "mo@example.com", "nia@example.com", "sue@example.com"],
        )
        message = next(m for m in mail.outbox if m.to == ["nia@example.com"])
        text = " ".join(message.body.split())
        self.assertEqual(message.subject, "BIOTech Futures – No Submission Received")
        self.assertIn("Dear members of No Entry,", text)
        self.assertIn("We did not receive a submission from your team.", text)
        day = FinalistEmailSettings.load().symposium_date
        self.assertIn(f"University of Sydney on {day:%A}, {day.day} {day:%B %Y} (in-person only)", text)
        self.assertIn("https://events.example.com/symposium", text)
        self.assertEqual(message.reply_to, ["support@biotechfutures.org"])

        self.assertEqual(results[-1]["teams"], {"total": 2, "emailed": 2})
        self.assertEqual(results[-1]["students"], {"total": 2, "emailed": 2, "times": {"total": 2, "emailed": 2}})
        self.assertEqual(NonSubmissionEmail.objects.count(), 2)
        # The two emails are recorded apart.
        self.assertFalse(NonFinalistEmail.objects.exists())

    def test_a_second_send_emails_nobody_again(self):
        self._send_all()
        mail.outbox = []
        self.assertTrue(self._send_all()[-1]["done"])
        self.assertEqual(mail.outbox, [])

    def test_it_waits_for_the_symposium_details_and_can_be_switched_off(self):
        FinalistEmailSettings.objects.update(registration_url="")
        r = self.client.post(reverse(NS_SEND), {}, format="json")
        self.assertEqual(
            r.json()["detail"], "Set the Symposium date and registration link on Notify Finalists before sending.",
        )
        FinalistEmailSettings.objects.update(registration_url="https://events.example.com/symposium")
        SystemEmailTemplate.objects.create(key="nonsubmission_notice", is_enabled=False)
        r = self.client.post(reverse(NS_SEND), {}, format="json")
        self.assertEqual(r.json()["detail"], "Non-submission notice is switched off on System Emails.")
        self.assertEqual(mail.outbox, [])

    def test_preview_is_addressed_to_the_first_team_due(self):
        r = self.client.post(reverse("grading:nonsubmission-email-preview"), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["subject"], "BIOTech Futures – No Submission Received")
        self.assertEqual(r.json()["to"], "No Entry")
        self.assertIn("At the Symposium you can:", r.json()["html"])
        self.assertEqual(mail.outbox, [])
