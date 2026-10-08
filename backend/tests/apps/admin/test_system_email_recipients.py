"""Who a System Emails test can be "of": each email's groups or people,
labelled as the page lists them, and a test carrying that one's own details
while codes and links that act for someone stay samples."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.services.system_email_recipients import RECIPIENTS, _people, recipient_context
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.services.email_registry import get_email_type
from apps.submissions.models import Submission
from apps.users.models import GuardianConsentRequest, StudentProfile, User
from apps.users.models.admin_scope import AdminScope

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
FRONTEND = "https://connect.example.com"


def _person(email, first, last, **extra):
    return User.objects.create_user(email=email, password="x", first_name=first, last_name=last, **extra)


def _join(user, group, role, **extra):
    return GroupMembership.objects.create(
        user=user, group=group, membership_role=role, joined_at=timezone.now() - timedelta(days=30), **extra,
    )


def _role(user, name):
    RoleAssignmentHistory.objects.create(
        user=user, role=Roles.objects.get_or_create(role_name=name)[0],
        valid_from=timezone.now() - timedelta(days=1),
    )


def _student(email, first, last, group, guardian=("Pat", "Parent", "pat@example.com")):
    user = _person(email, first, last)
    if group:
        _join(user, group, "student")
    else:
        _role(user, "student")
    StudentProfile.objects.create(
        user=user, pg_first_name=guardian[0], pg_last_name=guardian[1], pg_email=guardian[2],
        parent_guardian_flag=True, school_name="Test High", year_lvl="10",
    )
    return user


@override_settings(EMAIL_BACKEND=LOCMEM, FRONTEND_BASE_URL=FRONTEND)
class SystemEmailRecipientsTests(TestCase):
    def setUp(self):
        self.admin = _person("admin@example.com", "Ada", "Admin")
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

        self.btf2 = Groups.objects.create(group_name="BTF2")
        self.btf10 = Groups.objects.create(group_name="BTF10")
        self.amy = _student("amy@example.com", "Amy", "Chen", self.btf10)
        # Created without a guardian's name: the student's own sits in the guardian fields.
        self.ben = _student(
            "ben@example.com", "Ben", "Bell", self.btf2, guardian=("Ben", "Bell", "bell.home@example.com"),
        )
        self.aga = _person("aga@example.com", "Aga", "Smith")
        _join(self.aga, self.btf2, "mentor")
        _join(self.aga, self.btf10, "mentor")
        # A supervisor by role, and one by a supervisor place in a group.
        self.sam = _person("sam@example.com", "Sam", "Lee")
        _role(self.sam, "supervisor")
        _join(_person("sue@example.com", "Sue", "Ward"), self.btf10, "supervisor")
        # A student and a mentor with no group this year.
        self.nia = _student("nia@example.com", "Nia", "Lone", None, guardian=("Kim", "Lone", "kim@example.com"))
        _role(_person("max@example.com", "Max", "Free"), "mentor")

        # Not listed: last year's group of the same name, someone who left,
        # and a suspended account.
        old = Groups.objects.create(group_name="BTF2", year=timezone.now().year - 1)
        self.old = _student("old@example.com", "Olu", "Old", old)
        _join(_person("left@example.com", "Lee", "Left"), self.btf2, "student", left_at=timezone.now())
        _join(
            _person("off@example.com", "Sus", "Pended", account_status=User.AccountStatus.SUSPENDED),
            self.btf10, "student",
        )
        # Last year's student, never put in a group.
        _role(
            _person("past@example.com", "Pia", "Past", date_joined=timezone.now() - timedelta(days=400)),
            "student",
        )

        submission = Submission.objects.create(group=self.btf2, answers={"q_answers": "Answers."})
        submission.snapshot(self.ben)
        submission.save()

    def _recipients(self, key):
        response = self.client.get(f"/api/v1/admin/email-template/{key}/test-recipients/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()["data"]["recipients"]

    def _labels(self, key):
        return [option["label"] for option in self._recipients(key)]

    def _test(self, key, of):
        return self.client.post(
            f"/api/v1/admin/email-template/{key}/test-send/",
            {"to": "tester@example.com", "of": of},
            format="json",
        )

    def test_an_email_to_everyone_lists_students_and_mentors_by_group_then_supervisors_and_admins(self):
        self.assertEqual(
            self._labels("login_code"),
            [
                "(BTF2, BTF10, mentor) Aga Smith",
                "(BTF2) Ben Bell",
                "(BTF10) Amy Chen",
                "(NoGroup, mentor) Max Free",
                "(NoGroup) Nia Lone",
                "(supervisor) Sam Lee",
                "(supervisor) Sue Ward",
                "(admin) Ada Admin",
            ],
        )

    def test_someone_with_two_roles_is_listed_once(self):
        AdminScope.objects.create(user=self.sam)
        AdminScope.objects.create(user=self.aga)
        labels = self._labels("rsvp_reminder")

        self.assertIn("(supervisor) Sam Lee", labels)
        self.assertIn("(BTF2, BTF10, mentor) Aga Smith", labels)
        self.assertNotIn("(admin) Sam Lee", labels)
        self.assertNotIn("(admin) Aga Smith", labels)

    def test_the_unread_digest_lists_students_and_mentors_in_groups_only(self):
        self.assertEqual(
            self._labels("unread_messages"),
            ["(BTF2, BTF10, mentor) Aga Smith", "(BTF2) Ben Bell", "(BTF10) Amy Chen"],
        )

    def test_an_email_to_students_lists_students_only(self):
        self.assertEqual(
            self._labels("guardian_consent_student_notice"),
            ["(BTF2) Ben Bell", "(BTF10) Amy Chen", "(NoGroup) Nia Lone"],
        )

    def test_an_email_to_guardians_lists_each_by_their_students_group_and_name(self):
        self.assertEqual(
            self._labels("guardian_consent_request"),
            ["(BTF2, guardian) Ben Bell", "(BTF10, guardian) Amy Chen", "(NoGroup, guardian) Nia Lone"],
        )
        # A guardian with no email can't be sent it.
        StudentProfile.objects.filter(user=self.amy).update(pg_email="")
        self.assertEqual(
            self._labels("guardian_consent_request"),
            ["(BTF2, guardian) Ben Bell", "(NoGroup, guardian) Nia Lone"],
        )

    def test_a_list_of_mentors_only_shows_each_with_their_groups(self):
        self.assertEqual(
            [option["label"] for option in _people("mentor")],
            ["(BTF2, BTF10, mentor) Aga Smith", "(NoGroup, mentor) Max Free"],
        )

    def test_a_group_email_lists_groups_only(self):
        self.assertEqual(self._labels("submission_confirmation"), ["BTF2"])
        # Reminders go until a team submits.
        self.assertEqual(self._labels("submission_reminder"), ["BTF10"])

    def test_a_supervisor_email_lists_supervisors_by_their_role(self):
        audience = SimpleNamespace(supervisors=[self.sam])
        with patch("apps.management.services.results_notify.results_audience", return_value=audience):
            self.assertEqual(self._labels("results_supervisor"), ["(supervisor) Sam Lee"])

    def test_every_email_lists_and_fills_its_recipients_details(self):
        group_emails = {
            "submission_confirmation", "submission_reminder", "finalist_notification",
            "nonfinalist_invitation", "nonsubmission_notice", "results_team",
        }
        for key, recipients in RECIPIENTS.items():
            self.assertIsInstance(self._recipients(key), list, key)
            value = str(self.btf2.id if key in group_emails else self.ben.id)
            context = recipients.context(value)
            filled = {tag.context_key for tag in get_email_type(key).merge_tags} & set(context)
            self.assertTrue(filled, key)
            if key in group_emails:
                self.assertEqual(context["GROUP_NAME"], "BTF2", key)

    def test_an_email_with_nothing_of_a_persons_own_has_no_list(self):
        self.assertIsNone(self._recipients("announcement"))

    def test_an_unknown_email_is_not_found(self):
        response = self.client.get("/api/v1/admin/email-template/nope/test-recipients/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_person_email_carries_only_their_first_name(self):
        self.assertEqual(recipient_context("login_code", str(self.amy.id)), {"First_Name": "Amy"})

    def test_a_consent_request_names_the_real_guardian_but_keeps_the_sample_link(self):
        mail.outbox = []
        response = self._test("guardian_consent_request", str(self.amy.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Hi Pat,", html)
        self.assertIn("Amy Chen recently registered", html)
        self.assertIn("https://biotechfutures.org/#/consent/abc", html)
        self.assertNotIn(f"{FRONTEND}/#/consent/", html)
        # Nothing was issued, so no real link exists.
        self.assertFalse(GuardianConsentRequest.objects.exists())

    def test_a_guardian_name_copied_from_the_student_is_left_out(self):
        context = recipient_context("guardian_consent_request", str(self.ben.id))
        self.assertEqual(context["GUARDIAN_FIRST_NAME"], "")
        self.assertEqual(context["STUDENT_NAME"], "Ben Bell")

    def test_a_group_email_carries_the_groups_own_details(self):
        mail.outbox = []
        response = self._test("submission_reminder", str(self.btf10.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["sentTo"], "tester@example.com")
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Hi Group BTF10,", html)
        self.assertIn(f"{FRONTEND}/#/submission/{self.btf10.id}", html)

    def test_the_confirmation_names_who_submitted(self):
        context = recipient_context("submission_confirmation", str(self.btf2.id))
        self.assertEqual(context["GROUP_NAME"], "BTF2")
        self.assertEqual(str(context["SUBMITTED_BY"]), "Ben Bell")

    def test_someone_not_on_the_list_is_refused(self):
        mail.outbox = []
        for key, of in (
            ("login_code", str(self.old.id)),
            ("submission_confirmation", str(self.btf10.id)),
            ("announcement", str(self.amy.id)),
        ):
            response = self._test(key, of)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, key)
            self.assertEqual(response.json()["msg"], "Pick one from the list.")
        self.assertEqual(mail.outbox, [])

    def test_no_pick_keeps_the_samples(self):
        mail.outbox = []
        response = self._test("guardian_consent_request", "")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Alex Chen recently registered", mail.outbox[0].alternatives[0][0])

    # -- preview -------------------------------------------------------------

    def _preview(self, key, of):
        return self.client.post(
            f"/api/v1/admin/email-template/{key}/preview/", {"of": of}, format="json",
        )

    def test_the_preview_fills_in_the_one_picked_and_keeps_the_other_tags(self):
        response = self._preview("guardian_consent_request", str(self.amy.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        html = response.json()["data"]["html"]
        self.assertIn("Hi Pat,", html)
        self.assertIn("Amy Chen recently registered", html)
        # What isn't theirs still shows where it goes.
        self.assertIn("{{ consent_url }}", html)

    def test_the_preview_builds_a_groups_lists_from_their_details(self):
        response = self._preview("submission_reminder", str(self.btf10.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("BTF10", data["subject"])
        self.assertIn("Hi Group BTF10,", data["html"])
        self.assertIn("Poster", data["html"])
        self.assertNotIn("{{ required_components_list }}", data["html"])

    def test_the_preview_without_a_pick_shows_every_tag(self):
        response = self._preview("submission_reminder", "")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        html = response.json()["data"]["html"]
        self.assertIn("{{ group_name }}", html)
        self.assertIn("{{ required_components_list }}", html)

    def test_the_preview_refuses_someone_not_on_the_list(self):
        response = self._preview("login_code", str(self.old.id))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["msg"], "Pick one from the list.")
