"""The Symposium emails from the Email Nonfinalist tab, to teams that
submitted but weren't picked and to teams that didn't submit: who gets them,
the client's wording with the Symposium details from Notify Finalists,
preview, and sending in batches."""
from datetime import timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import FinalistFlag
from apps.groups.models import GroupMembership, Groups
from apps.management.models import EmailDelivery, FinalistEmailSettings, NonFinalistEmail, NonSubmissionEmail
from apps.management.services.finalist_notify import symposium_today
from apps.services.models import SystemEmailTemplate
from apps.submissions.models import Deadline, GroupExtension, Submission
from apps.users.models import User

from tests.apps.grading.fixtures import _GradingFixture, just_closed

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
SEND = "management:nonfinalist-email-send"
NS_SEND = "management:nonsubmission-email-send"


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


def _recipients():
    """Everyone the emails went to, To and CC."""
    return sorted(address for m in mail.outbox for address in m.to + m.cc)


def _press(test, name):
    """One press: the run sends every team (inline under test settings). The
    run's result, with the counts after it, as a one-item list."""
    r = test.client.post(reverse(name), {}, format="json")
    test.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
    body = r.json()
    test.assertFalse(body["sending"])
    return [{**body, "emailed": body["run"]["emailed"], "failed": body["run"]["failed"]}]


def _press_which(test, name, which):
    """Email Newly Added (``"new"``) or Resend Email To Missed Individuals
    (``"missed"``): the run's result, with the counts after it."""
    r = test.client.post(reverse(name), {"which": which}, format="json")
    test.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
    return r.json()


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

        # A finalist team and a team that never submitted don't get it. The
        # finalists have been told, so who wasn't picked is settled.
        finalist = _submitted_team("Picked", self.staff)
        _member("fin@example.com", finalist)
        FinalistFlag.objects.create(
            group=finalist, flagged_by=self.staff, notified=True, notified_at=timezone.now(),
        )
        no_entry = Groups.objects.create(group_name="No Entry")
        _member("none@example.com", no_entry)

        details = FinalistEmailSettings.load()
        details.symposium_date = symposium_today() + timedelta(days=30)
        details.registration_url = "https://events.example.com/symposium"
        details.save()

    def _send_all(self):
        return _press(self, SEND)

    def test_every_current_member_of_a_team_not_picked_gets_it(self):
        results = self._send_all()
        # One email: the students in To, the mentor and supervisor in CC.
        self.assertEqual(
            [(m.to, m.cc) for m in mail.outbox],
            [(["amy@example.com", "ben@example.com"], ["mo@example.com", "sue@example.com"])],
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
        self.assertEqual(self._send_all()[-1]["run"]["due"], 0)
        self.assertEqual(mail.outbox, [])

    def test_one_press_emails_every_team(self):
        for n in range(6):
            _member(f"extra{n}@example.com", _submitted_team(f"Extra {n}", self.staff))
        result = self._send_all()[-1]
        # The fixture team has four members; six more teams of one.
        self.assertEqual((result["run"]["due"], result["emailed"], result["run"]["failed"]), (10, 10, 0))
        self.assertEqual(result["teams"], {"total": 7, "emailed": 7})

    def test_a_team_whose_member_misses_it_stays_pending(self):
        # An earlier send reached everyone but ben; this one doesn't go at all.
        for address in ("amy@example.com", "mo@example.com", "sue@example.com"):
            EmailDelivery.objects.create(email="nonfinalist_invitation", group=self.group, address=address)
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("rejected")), \
                self.assertLogs("apps.management.services.delivery", level="ERROR"):
            results = self._send_all()
        self.assertEqual(sum(r["failed"] for r in results), 1)
        # The page lists who it couldn't reach, and why.
        self.assertEqual(
            results[-1]["run"]["missed"], [{"who": f"ben@example.com ({self.group.group_name}, Mem ben)", "reason": "lost the mail server connection"}],
        )
        # The student it reached counts as emailed; ben doesn't.
        self.assertEqual(results[-1]["students"], {"total": 2, "emailed": 1, "times": {"total": 2, "emailed": 1}})
        # The group counts as emailed, though it isn't done until ben has it.
        self.assertEqual((results[-1]["groups"], results[-1]["teams"]), ({"total": 1, "emailed": 1}, {"total": 1, "emailed": 0}))
        self.assertFalse(NonFinalistEmail.objects.filter(group=self.group).exists())

        # The next press emails only the member it missed.
        mail.outbox = []
        result = self._send_all()[-1]
        self.assertEqual([(m.to, m.cc) for m in mail.outbox], [(["ben@example.com"], [])])
        self.assertEqual(result["run"]["due"], 1)
        self.assertTrue(NonFinalistEmail.objects.filter(group=self.group).exists())

    def test_newly_added_and_resend_to_those_missed_each_email_only_their_own(self):
        # An earlier send reached everyone but ben; this one doesn't go at all.
        for address in ("amy@example.com", "mo@example.com", "sue@example.com"):
            EmailDelivery.objects.create(email="nonfinalist_invitation", group=self.group, address=address)
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("rejected")), \
                self.assertLogs("apps.management.services.delivery", level="ERROR"):
            result = self._send_all()[-1]
        self.assertEqual(result["waiting"]["missed"], {"teams": 1, "people": 1})
        # A team that submitted since hasn't been tried, so isn't resent to.
        _member("new@example.com", _submitted_team("Late", self.staff))

        mail.outbox = []
        result = _press_which(self, SEND, "missed")
        self.assertEqual([(m.to, m.cc) for m in mail.outbox], [(["ben@example.com"], [])])
        self.assertEqual(result["waiting"], {"new": {"teams": 1, "people": 1}, "missed": {"teams": 0, "people": 0}})
        self.assertEqual(result["teams"], {"total": 2, "emailed": 1})

        # Email Newly Added emails only the team that submitted since.
        mail.outbox = []
        result = _press_which(self, SEND, "new")
        self.assertEqual([m.to for m in mail.outbox], [["new@example.com"]])
        self.assertEqual(result["waiting"], {"new": {"teams": 0, "people": 0}, "missed": {"teams": 0, "people": 0}})
        self.assertEqual(result["teams"], {"total": 2, "emailed": 2})

    def test_resend_refuses_an_unknown_which(self):
        r = self.client.post(reverse(SEND), {"which": "everyone"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sending_waits_for_the_symposium_details_on_notify_finalists(self):
        FinalistEmailSettings.objects.update(symposium_date=None)
        r = self.client.post(reverse(SEND), {}, format="json")
        self.assertEqual(
            r.json()["detail"], "Set the Symposium date and registration link on Notify Finalists before sending.",
        )
        self.assertEqual(self.client.get(reverse("management:nonfinalist-email")).json()["blocked"], r.json()["detail"])

        FinalistEmailSettings.objects.update(symposium_date=symposium_today() - timedelta(days=1))
        r = self.client.post(reverse(SEND), {}, format="json")
        self.assertEqual(
            r.json()["detail"], "The Symposium date on Notify Finalists is before today. Update it before sending.",
        )
        self.assertEqual(mail.outbox, [])

    def test_it_waits_until_the_finalists_are_notified(self):
        # Picked but not yet told: the picks may still change.
        FinalistFlag.objects.update(notified=False, notified_at=None)
        r = self.client.post(reverse(SEND), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.json()["detail"], "Notify the finalists on Notify Finalists before sending this.")
        self.assertEqual(self.client.get(reverse("management:nonfinalist-email")).json()["blocked"], r.json()["detail"])
        self.assertEqual(mail.outbox, [])

    def test_neither_email_goes_out_while_submissions_are_open(self):
        # Past the date the teams were shown, but still in its grace hours.
        closes_at = timezone.now() - timedelta(hours=1)
        Deadline.objects.create(closes_at=closes_at, grace_hours=2)
        until = timezone.localtime(closes_at + timedelta(hours=2), ZoneInfo("Australia/Sydney"))
        for name in (SEND, NS_SEND):
            r = self.client.post(reverse(name), {}, format="json")
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
            detail = r.json()["detail"]
            self.assertTrue(detail.startswith("Submissions are open until "), detail)
            self.assertIn(f"{until.day} {until:%B %Y}, ", detail)
            self.assertTrue(detail.endswith("(Sydney time). Send this once they close."), detail)
        self.assertEqual(mail.outbox, [])

    def test_neither_email_goes_out_while_any_extension_is_open(self):
        # The deadline has closed, but one team's extension, with its grace
        # hours, hasn't: that team may yet submit, or be picked.
        Deadline.objects.create(closes_at=just_closed())
        extension = GroupExtension.objects.create(
            group=Groups.objects.create(group_name="Extended"),
            extended_until=timezone.now() - timedelta(hours=1), grace_hours=2,
        )
        until = timezone.localtime(extension.extended_until + timedelta(hours=2), ZoneInfo("Australia/Sydney"))
        for name in (SEND, NS_SEND):
            r = self.client.post(reverse(name), {}, format="json")
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
            detail = r.json()["detail"]
            self.assertTrue(detail.startswith("A team's extension is open until "), detail)
            self.assertIn(f"{until.day} {until:%B %Y}, ", detail)
            self.assertTrue(detail.endswith("(Sydney time). Send this once every extension has ended."), detail)
        self.assertEqual(mail.outbox, [])

        # Once it has ended, grace hours included, or is revoked, sending goes ahead.
        GroupExtension.objects.filter(pk=extension.pk).update(extended_until=timezone.now() - timedelta(hours=3))
        self.assertEqual(self.client.get(reverse("management:nonfinalist-email")).json()["blocked"], "")
        GroupExtension.objects.filter(pk=extension.pk).update(
            extended_until=timezone.now() + timedelta(days=1), revoked_at=timezone.now(),
        )
        self._send_all()
        self.assertEqual(len(_recipients()), 4)

    def test_a_send_pressed_while_another_runs_is_queued_until_it_finishes(self):
        from apps.management.models import EmailSendRun

        # Another email's run, e.g. Notify Finalists.
        EmailSendRun.objects.create(
            key="finalist_notification", held_until=timezone.now() + timedelta(minutes=4), started_at=timezone.now(),
        )
        r = self.client.post(reverse(SEND), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual((r.json()["sending"], r.json()["queued"]), (False, 1))
        self.assertEqual(r.json()["ahead"], ["Finalist notification"])
        self.assertEqual(mail.outbox, [])

        # Once that run finishes, the page's next check sends it.
        EmailSendRun.objects.filter(key="finalist_notification").update(held_until=None, finished_at=timezone.now())
        body = self.client.get(reverse("management:nonfinalist-email")).json()
        self.assertEqual((body["queued"], body["teams"]["emailed"]), (0, 1))
        self.assertEqual(len(_recipients()), 4)

        # The other email has a send of its own.
        self.assertFalse(self.client.get(reverse("management:nonsubmission-email")).json()["sending"])

        # A run that died frees it once its hold lapses.
        EmailSendRun.objects.update(held_until=timezone.now() - timedelta(seconds=1))
        self.assertFalse(self.client.get(reverse("management:nonfinalist-email")).json()["sending"])
        self._send_all()
        self.assertEqual(len(_recipients()), 4)
        self.assertIsNone(EmailSendRun.objects.get(key="nonfinalist_invitation").held_until)

    def test_a_switched_off_email_is_refused(self):
        SystemEmailTemplate.objects.create(key="nonfinalist_invitation", is_enabled=False)
        r = self.client.post(reverse(SEND), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.json()["detail"], "Non-finalist invitation is switched off on System Emails.")

    def test_the_tab_shows_who_it_is_for(self):
        r = self.client.get(reverse("management:nonfinalist-email"))
        # The student who left isn't counted.
        self.assertEqual(r.json(), {
            "teams": {"total": 1, "emailed": 0},
            "groups": {"total": 1, "emailed": 0},
            "students": {"total": 2, "emailed": 0, "times": {"total": 2, "emailed": 0}},
            "mentors": {"total": 1, "emailed": 0, "times": {"total": 1, "emailed": 0}},
            "supervisors": {"total": 1, "emailed": 0, "times": {"total": 1, "emailed": 0}},
            # Nobody tried yet: the team is newly added.
            "waiting": {"new": {"teams": 1, "people": 4}, "missed": {"teams": 0, "people": 0}},
            "blocked": "",
            "sending": False,
            "queued": 0,
            "ahead": [],
            "sent_from": "info@biotechfutures.org",
            "run": None,
        })

    def test_preview_is_addressed_to_the_first_team_due(self):
        r = self.client.post(reverse("management:nonfinalist-email-preview"), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["to"], self.group.group_name)
        self.assertIn('href="https://events.example.com/symposium"', r.json()["html"])
        self.assertIn("Register to Attend (In-Person)", r.json()["html"])
        self.assertEqual(mail.outbox, [])

    def test_graders_only(self):
        self.client.force_authenticate(self.non_staff)
        for name in ("management:nonfinalist-email", "management:nonsubmission-email"):
            self.assertEqual(self.client.get(reverse(name)).status_code, status.HTTP_403_FORBIDDEN)
        for name in ("management:nonfinalist-email-preview", SEND, "management:nonsubmission-email-preview", NS_SEND):
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
        return _press(self, NS_SEND)

    def test_the_section_counts_teams_that_did_not_submit(self):
        r = self.client.get(reverse("management:nonsubmission-email"))
        # Not the mentor of the group that never entered.
        self.assertEqual(r.json(), {
            "teams": {"total": 2, "emailed": 0},
            "groups": {"total": 2, "emailed": 0},
            "students": {"total": 2, "emailed": 0, "times": {"total": 2, "emailed": 0}},
            "mentors": {"total": 1, "emailed": 0, "times": {"total": 1, "emailed": 0}},
            "supervisors": {"total": 1, "emailed": 0, "times": {"total": 1, "emailed": 0}},
            "waiting": {"new": {"teams": 2, "people": 4}, "missed": {"teams": 0, "people": 0}},
            "blocked": "",
            "sending": False,
            "queued": 0,
            "ahead": [],
            "sent_from": "info@biotechfutures.org",
            "run": None,
        })

    def test_everyone_counts_as_emailed_once_their_team_is(self):
        self._send_all()
        r = self.client.get(reverse("management:nonsubmission-email")).json()
        self.assertEqual(
            (r["students"], r["mentors"], r["supervisors"]),
            ({"total": 2, "emailed": 2, "times": {"total": 2, "emailed": 2}}, {"total": 1, "emailed": 1, "times": {"total": 1, "emailed": 1}}, {"total": 1, "emailed": 1, "times": {"total": 1, "emailed": 1}}),
        )

    def test_a_mentor_on_two_teams_is_one_person_emailed_twice(self):
        # The team that saved a draft shares its supervisor with the other.
        sue = GroupMembership.objects.get(user__email="sue@example.com").user
        GroupMembership.objects.create(group=self.draft, user=sue, membership_role="supervisor")
        r = self.client.get(reverse("management:nonsubmission-email")).json()
        self.assertEqual(r["supervisors"], {"total": 1, "emailed": 0, "times": {"total": 2, "emailed": 0}})
        self._send_all()
        r = self.client.get(reverse("management:nonsubmission-email")).json()
        self.assertEqual(r["supervisors"], {"total": 1, "emailed": 1, "times": {"total": 2, "emailed": 2}})

    def test_every_current_member_of_a_team_that_did_not_submit_gets_it(self):
        results = self._send_all()
        self.assertEqual(_recipients(), ["dee@example.com", "mo@example.com", "nia@example.com", "sue@example.com"])
        message = next(m for m in mail.outbox if "nia@example.com" in m.to)
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
        self.assertEqual(self._send_all()[-1]["run"]["due"], 0)
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

    def test_a_team_on_an_extension_blocks_it_for_everyone(self):
        Deadline.objects.create(closes_at=just_closed())
        GroupExtension.objects.create(group=self.no_entry, extended_until=timezone.now() + timedelta(hours=5))
        blocked = self.client.get(reverse("management:nonsubmission-email")).json()["blocked"]
        self.assertTrue(blocked.startswith("A team's extension is open until "), blocked)
        r = self.client.post(reverse(NS_SEND), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(mail.outbox, [])

    def test_an_extension_from_another_year_does_not_block_it(self):
        Deadline.objects.create(closes_at=just_closed())
        past_team = Groups.objects.create(group_name="Last Year", year=self.no_entry.year - 1)
        GroupExtension.objects.create(group=past_team, extended_until=timezone.now() + timedelta(days=1))
        self.assertEqual(self.client.get(reverse("management:nonsubmission-email")).json()["blocked"], "")

    def test_it_does_not_wait_for_the_finalists(self):
        # Teams that didn't submit were never in the running.
        self.assertFalse(FinalistFlag.objects.exists())
        self.assertEqual(self.client.get(reverse("management:nonsubmission-email")).json()["blocked"], "")

    def test_preview_is_addressed_to_the_first_team_due(self):
        r = self.client.post(reverse("management:nonsubmission-email-preview"), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["subject"], "BIOTech Futures – No Submission Received")
        self.assertEqual(r.json()["to"], "No Entry")
        self.assertIn("At the Symposium you can:", r.json()["html"])
        self.assertEqual(mail.outbox, [])
