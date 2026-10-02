"""Send Test Email on the email tabs: which group or supervisor each email can
be tested as, and a test going to any address exactly as the chosen one would
get it, with nothing recorded as sent."""
from datetime import timedelta
from email.mime.base import MIMEBase

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import FinalistFlag
from apps.groups.models import GroupMembership, Groups
from apps.management.models import (
    CertificatesRelease,
    FinalistEmailSettings,
    MarksRelease,
    NonFinalistEmail,
    ResultsEmailSettings,
    ResultsTeamEmail,
)
from apps.management.services.finalist_notify import symposium_today
from apps.services.models import SystemEmailTemplate
from apps.submissions.models import Submission
from apps.users.models import StudentProfile, SupervisorProfile, User

from tests.apps.grading.fixtures import _GradingFixture
from tests.apps.management.fixtures import _seed_doc_templates

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def _member(email, group, role="student", supervisor=None):
    user = User.objects.create_user(email=email, first_name="Mem", last_name=email.split("@")[0], password="pw12345!")
    GroupMembership.objects.create(
        user=user, group=group, membership_role=role, joined_at=timezone.now() - timedelta(days=30),
    )
    if role == "student":
        StudentProfile.objects.create(
            user=user, pg_first_name="P", pg_last_name="G", parent_guardian_flag=True,
            school_name="Test School", year_lvl="10", supervisor=supervisor,
        )
    return user


def _submitted_team(name, staff):
    team = Groups.objects.create(group_name=name)
    submission = Submission.objects.create(group=team, answers={"q_answers": "Answers."})
    submission.snapshot(staff)
    submission.save()
    return team


@override_settings(EMAIL_BACKEND=LOCMEM)
class TestEmailTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

        self.supervisor = User.objects.create_user(
            email="sam.lee@example.com", first_name="Sam", last_name="Lee", password="pw12345!",
        )
        profile = SupervisorProfile.objects.create(user=self.supervisor)
        # The fixture team submitted and wasn't picked.
        self.amy = _member("amy@example.com", self.group, supervisor=profile)
        self.mo = _member("mo@example.com", self.group, role="mentor")
        # A finalist team and a team that didn't submit.
        self.picked = _submitted_team("Picked", self.staff)
        _member("fin@example.com", self.picked)
        FinalistFlag.objects.create(group=self.picked, flagged_by=self.staff)
        self.no_entry = Groups.objects.create(group_name="No Entry")
        _member("nia@example.com", self.no_entry)

        details = FinalistEmailSettings.load()
        details.symposium_date = symposium_today() + timedelta(days=30)
        details.confirm_by = symposium_today() + timedelta(days=10)
        details.slides_due = symposium_today() + timedelta(days=20)
        details.registration_url = "https://events.example.com/symposium"
        details.save()
        results = ResultsEmailSettings.load()
        results.survey_closes = symposium_today() + timedelta(days=30)
        results.save()
        for model in (MarksRelease, CertificatesRelease):
            row = model.load()
            row.released_at = timezone.now()
            row.save()
        _seed_doc_templates()

    def _options(self, kind):
        r = self.client.get(reverse("management:test-email", args=[kind]))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        return r.json()["recipients"]

    def _send(self, kind, recipient, to="tester@example.com", **fields):
        return self.client.post(
            reverse("management:test-email", args=[kind]),
            {"recipient": recipient, "to": to, **fields},
            format="json",
        )

    def test_each_email_lists_the_groups_it_can_go_to(self):
        # Each group gets one email, so the list is groups, by name.
        team = self.group.group_name
        self.assertEqual(self._options("nonfinalists"), [{"value": str(self.group.id), "label": team}])
        self.assertEqual([o["label"] for o in self._options("nonsubmissions")], ["No Entry"])
        self.assertEqual([o["label"] for o in self._options("finalist")], ["Picked"])
        # Not finalists while certificates exclude them.
        self.assertEqual([o["label"] for o in self._options("results-groups")], [team])
        self.assertEqual(self._options("results-supervisors"), [{"value": str(self.supervisor.id), "label": "Sam Lee"}])

    def test_a_test_goes_to_the_typed_address_as_the_chosen_team_gets_it(self):
        option = self._options("nonfinalists")[0]
        r = self._send("nonfinalists", option["value"])
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        # And where it comes back to if it can't be delivered.
        self.assertEqual(r.json(), {"sent_to": "tester@example.com", "sent_from": "info@biotechfutures.org"})
        [message] = mail.outbox
        self.assertEqual(message.to, ["tester@example.com"])
        self.assertEqual(message.subject, "Thank you for your submission – Invitation to the Symposium")
        self.assertIn(f"Dear members of {self.group.group_name},", " ".join(message.body.split()))
        # A test isn't the real thing: the team still hasn't had it.
        self.assertFalse(NonFinalistEmail.objects.exists())

    def test_it_goes_even_while_the_email_is_switched_off(self):
        SystemEmailTemplate.objects.create(key="nonsubmission_notice", is_enabled=False)
        r = self._send("nonsubmissions", self._options("nonsubmissions")[0]["value"])
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertIn("Dear members of No Entry,", " ".join(mail.outbox[0].body.split()))

    def test_the_finalist_test_uses_the_unsaved_details_like_the_preview(self):
        r = self._send(
            "finalist", self._options("finalist")[0]["value"],
            registration_url="https://events.example.com/draft",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertIn("https://events.example.com/draft", mail.outbox[0].body)
        self.assertEqual(FinalistEmailSettings.load().registration_url, "https://events.example.com/symposium")

    def test_results_tests_carry_their_files_and_record_nothing(self):
        self.assertEqual(self._send("results-groups", str(self.group.id)).status_code, status.HTTP_200_OK)
        self.assertEqual(self._send("results-supervisors", str(self.supervisor.id)).status_code, status.HTTP_200_OK)
        year = self.group.year
        files = [
            [a[0] for a in m.attachments if not isinstance(a, MIMEBase)]
            for m in mail.outbox
        ]
        self.assertEqual(files, [
            [
                f"{year}_BTF_Student_Certificate_Mem_amy.docx",
                f"{year}_BTF_Mentor_Certificate_Mem_mo.docx",
                f"{year}_BTF_Marks_BTF-TEST-1.docx",
            ],
            [
                f"{year}_BTF_Student_Certificate_Mem_amy.docx",
                f"{year}_BTF_Mentor_Certificate_Mem_mo.docx",
                f"{year}_BTF_Student_Marks_Sam_Lee.xlsx",
            ],
        ])
        self.assertEqual([m.to for m in mail.outbox], [["tester@example.com"]] * 2)
        self.assertFalse(ResultsTeamEmail.objects.exists())

    def test_it_says_what_is_wrong(self):
        value = self._options("nonfinalists")[0]["value"]
        self.assertEqual(self._send("nonfinalists", value, to="not-an-address").json()["detail"], "Enter a valid email address.")
        self.assertEqual(self._send("nonfinalists", value, to="").json()["detail"], "Enter an email address.")
        # A group that isn't on that email's list, such as a finalist for the non-finalist email.
        other = self._options("finalist")[0]["value"]
        self.assertEqual(self._send("nonfinalists", other).json()["detail"], "Pick one from the list.")
        self.assertEqual(self._send("nonfinalists", "").json()["detail"], "Pick one from the list.")
        self.assertEqual(mail.outbox, [])

    def test_unknown_emails_and_non_graders_are_refused(self):
        self.assertEqual(self.client.get(reverse("management:test-email", args=["nope"])).status_code, 404)
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(
            self.client.get(reverse("management:test-email", args=["finalist"])).status_code, status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self._send("finalist", "1").status_code, status.HTTP_403_FORBIDDEN)

    # -- the preview follows the group picked -----------------------------------------

    def _value(self, kind, label):
        return next(o["value"] for o in self._options(kind) if o["label"] == label)

    def test_the_finalist_preview_is_addressed_to_the_picked_group(self):
        other = _submitted_team("Zed Pick", self.staff)
        _member("zed@example.com", other)
        FinalistFlag.objects.create(group=other, flagged_by=self.staff)
        url = reverse("management:finalist-email-preview")
        # Nobody picked: the first team not yet emailed.
        self.assertEqual(self.client.post(url, {}, format="json").json()["group_name"], "Picked")
        r = self.client.post(url, {"recipient": self._value("finalist", "Zed Pick")}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["group_name"], "Zed Pick")
        self.assertIn("Zed Pick", r.json()["html"])

    def test_the_symposium_previews_are_addressed_to_the_picked_group(self):
        other = Groups.objects.create(group_name="Zed None")
        _member("zoe@example.com", other)
        url = reverse("management:nonsubmission-email-preview")
        self.assertEqual(self.client.post(url, {}, format="json").json()["to"], "No Entry")
        r = self.client.post(url, {"recipient": self._value("nonsubmissions", "Zed None")}, format="json")
        self.assertEqual(r.json()["to"], "Zed None")
        self.assertIn("Zed None", r.json()["html"])
        # A group from the other email's list isn't on this one.
        team = self._value("nonfinalists", self.group.group_name)
        r = self.client.post(url, {"recipient": team}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.json()["detail"], "Pick one from the list.")

    def test_the_results_previews_show_the_picked_ones_email_and_files(self):
        other = _submitted_team("Zed Team", self.staff)
        _member("zed@example.com", other)
        url = reverse("management:results-email-preview")
        year = self.group.year
        r = self.client.post(url, {
            "audience": "groups", "recipient": self._value("results-groups", "Zed Team"),
            "survey_url": "https://example.com/draft",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["to"], "Zed Team")
        # With the page's unsaved details, as without a pick.
        self.assertIn('href="https://example.com/draft"', r.json()["html"])
        self.assertEqual(r.json()["attachments"], [
            f"{year}_BTF_Student_Certificate_Mem_zed.docx", f"{year}_BTF_Marks_Zed_Team.docx",
        ])

        r = self.client.post(url, {"audience": "supervisors", "recipient": str(self.supervisor.id)}, format="json")
        self.assertEqual(r.json()["to"], "Sam Lee")
        self.assertEqual(r.json()["attachments"][-1], f"{year}_BTF_Student_Marks_Sam_Lee.xlsx")
        # Nothing was sent or recorded.
        self.assertEqual(mail.outbox, [])
        self.assertFalse(ResultsTeamEmail.objects.exists())

    def test_groups_are_listed_in_number_order(self):
        # BTF2 before BTF10, not after it as plain text order would put it.
        for name in ("BTF10", "BTF2", "BTF1"):
            _member(f"{name.lower()}@example.com", Groups.objects.create(group_name=name))
        self.assertEqual(
            [o["label"] for o in self._options("nonsubmissions")],
            ["BTF1", "BTF2", "BTF10", "No Entry"],
        )
