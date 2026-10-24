"""The supervisors' weekly registration status email (the spec's "Supervisor
Weekly Digest"), and Management > Challenge Start, whose date it names."""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.management.models import ChallengeStart
from apps.services.models import SystemEmailTemplate
from apps.services.system_email import render_system_email
from apps.submissions.services import current_cohort
from apps.users.models import StudentProfile, SupervisorProfile, User
from apps.users.supervisor_status import send_due, status_context, status_counts, supervisors_due

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
FRONTEND = "https://connect.example.com"


def _supervisor(email, first="Sam"):
    user = User.objects.create_user(
        email=email, first_name=first, last_name="Lee", account_status=User.AccountStatus.ACTIVE,
    )
    return user, SupervisorProfile.objects.create(user=user, school_name="Test High")


def _student(email, supervisor, *, guardian_email="", permission=False):
    user = User.objects.create_user(
        email=email, first_name="Amy", last_name="Chen", account_status=User.AccountStatus.PENDING,
    )
    StudentProfile.objects.create(
        user=user, supervisor=supervisor, school_name="Test High", year_lvl="10",
        pg_first_name="Pat" if guardian_email else "", pg_last_name="Parent" if guardian_email else "",
        pg_email=guardian_email or None, parent_guardian_flag=bool(guardian_email),
        has_join_permission=permission, registered_by=StudentProfile.RegisteredBy.SUPERVISOR,
    )
    return user


@override_settings(EMAIL_BACKEND=LOCMEM, FRONTEND_BASE_URL=FRONTEND, EMAIL_JOBS_TOKEN="secret-token")
class SupervisorRegistrationStatusTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.sam, self.profile = _supervisor("sam@school.test")
        _student("done@example.com", self.profile, guardian_email="g1@example.com", permission=True)
        _student("signing@example.com", self.profile, guardian_email="g2@example.com")
        _student("contact@example.com", self.profile)
        # Every one of Kim's students is complete: nothing for Kim.
        self.kim, kim_profile = _supervisor("kim@school.test", first="Kim")
        _student("kims@example.com", kim_profile, guardian_email="g3@example.com", permission=True)

    def test_counts_its_students_as_my_students_does(self):
        self.assertEqual(status_counts(self.sam.id), {"complete": 1, "pending_signature": 1, "pending_contact": 1})

    def test_once_a_week_to_each_supervisor_with_a_student_still_pending(self):
        self.assertEqual(list(supervisors_due()), [self.profile])
        self.assertEqual(send_due(), {"sent": 1, "failed": 0})
        [message] = mail.outbox
        self.assertEqual(message.to, ["sam@school.test"])
        self.assertEqual(message.subject, "BIOTech Futures: Student Registration Status")
        html = message.alternatives[0][0]
        for text in ("Hi Sam,", "Pending Signature", "Pending Contact", f"{FRONTEND}/#/my-students"):
            self.assertIn(text, html)
        # Already emailed today: the next run sends nothing.
        self.assertEqual(send_due(), {"sent": 0, "failed": 0})
        self.assertEqual(len(mail.outbox), 1)

        # Not again for a week: emailed 6 days ago, still skipped; 7, due.
        today = timezone.localdate()
        SupervisorProfile.objects.filter(pk=self.profile.pk).update(status_digest_sent_on=today - timedelta(days=6))
        self.assertEqual(list(supervisors_due()), [])
        SupervisorProfile.objects.filter(pk=self.profile.pk).update(status_digest_sent_on=today - timedelta(days=7))
        self.assertEqual(list(supervisors_due()), [self.profile])

    def test_stops_once_all_their_students_are_complete(self):
        StudentProfile.objects.filter(supervisor=self.profile).update(
            has_join_permission=True, pg_first_name="Pat", pg_last_name="Parent", pg_email="g@example.com",
            parent_guardian_flag=True,
        )
        self.assertEqual(list(supervisors_due()), [])

    def test_nothing_while_its_switched_off(self):
        SystemEmailTemplate.objects.create(key="supervisor_registration_status", is_enabled=False)
        self.assertEqual(send_due(), {"sent": 0, "failed": 0, "disabled": True})
        self.assertEqual(mail.outbox, [])

    def test_names_the_challenge_start_once_its_set(self):
        rendered = render_system_email("supervisor_registration_status", status_context(self.sam))
        self.assertIn("by the challenge start date will not", rendered.html)
        # 13:59 UTC is 23:59 on 27 July in Sydney.
        ChallengeStart.objects.update_or_create(
            year=current_cohort(), defaults={"starts_at": datetime(2026, 7, 27, 13, 59, tzinfo=dt_timezone.utc)},
        )
        rendered = render_system_email("supervisor_registration_status", status_context(self.sam))
        self.assertIn("by the challenge start date of 27 July will not", rendered.html)
        # Its day is Sydney's: 15:00 UTC on the 27th is 1 am on the 28th there.
        ChallengeStart.objects.filter(year=current_cohort()).update(
            starts_at=datetime(2026, 7, 27, 15, 0, tzinfo=dt_timezone.utc),
        )
        rendered = render_system_email("supervisor_registration_status", status_context(self.sam))
        self.assertIn("by the challenge start date of 28 July will not", rendered.html)

    def test_the_job_needs_the_token(self):
        url = "/api/v1/admin/send-supervisor-registration-status/"
        self.assertEqual(APIClient().post(url).status_code, 401)
        response = APIClient().post(url, HTTP_X_EMAIL_JOBS_TOKEN="secret-token")
        self.assertEqual(response.status_code, 202)


class ChallengeStartTests(TestCase):
    URL = "/api/v1/management/challenge-start/"

    def setUp(self):
        self.staff = User.objects.create_user(
            email="staff@example.test", first_name="Staff", last_name="Member", is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_staff_set_and_clear_it_and_see_who_did(self):
        self.assertEqual(self.client.get(self.URL).json()["starts_at"], None)
        state = self.client.put(self.URL, {"starts_at": "2026-07-27T13:59:00Z"}, format="json").json()
        self.assertEqual((state["starts_at"], state["set_by"]), ("2026-07-27T13:59:00+00:00", "Staff Member"))
        self.assertEqual(self.client.get(self.URL).json()["starts_at"], "2026-07-27T13:59:00+00:00")
        self.assertEqual(self.client.put(self.URL, {"starts_at": None}, format="json").json()["starts_at"], None)
        self.assertEqual(self.client.put(self.URL, {"starts_at": "soon"}, format="json").status_code, 400)

    def test_only_staff(self):
        member = User.objects.create_user(email="member@example.test")
        client = APIClient()
        client.force_authenticate(member)
        self.assertEqual(client.get(self.URL).status_code, 403)
