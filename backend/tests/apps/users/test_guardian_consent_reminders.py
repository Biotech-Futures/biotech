"""The consent form reminders: a guardian who hasn't signed is emailed the
form as soon as a student names them, and then every day until they sign,
each time with a fresh link. The student hears once that it went."""
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.role_names import ROLE_STUDENT
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.services.models import SystemEmailTemplate
from apps.users.guardian_reminders import guardians_due, send_due
from apps.users.models import GuardianConsentRequest, StudentProfile, User

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
FRONTEND = "https://connect.example.com"


def _student(email, guardian_email="pat@example.com", **user_fields):
    user_fields.setdefault("account_status", User.AccountStatus.PENDING)
    user = User.objects.create_user(email=email, first_name="Amy", last_name="Chen", **user_fields)
    profile = StudentProfile.objects.create(
        user=user, pg_first_name="Pat", pg_last_name="Parent", pg_email=guardian_email,
        parent_guardian_flag=True, school_name="Test High", year_lvl="10",
    )
    return user, profile


@override_settings(
    EMAIL_BACKEND=LOCMEM, FRONTEND_BASE_URL=FRONTEND,
    GUARDIAN_REMINDER_INTERVAL_DAYS=1, GUARDIAN_REMINDER_TOKEN="secret-token",
)
class GuardianConsentReminderTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.student, self.profile = _student("amy@example.com")

    def _to(self, address):
        return [message for message in mail.outbox if message.to == [address]]

    def _a_day_later(self):
        """Move the last send back a day, as if tomorrow's run had come."""
        yesterday = timezone.now() - timedelta(days=1)
        GuardianConsentRequest.objects.filter(student=self.profile).update(created_at=yesterday)
        StudentProfile.objects.filter(pk=self.profile.pk).update(
            guardian_reminder_sent_at=yesterday, guardian_reminder_due_at=timezone.now(),
        )

    # -- the daily run ---------------------------------------------------------

    def test_the_daily_run_emails_a_guardian_nobody_has_emailed_yet(self):
        self.assertEqual(send_due(), {"sent": 1, "failed": 0, "skipped": 0})

        [request] = self._to("pat@example.com")
        self.assertEqual(request.subject, "Action Required: Sign parent/guardian permission form")
        self.assertIn(f"{FRONTEND}/#/consent/", request.alternatives[0][0])
        # The student hears that it went.
        self.assertEqual(len(self._to("amy@example.com")), 1)

    def test_a_second_run_the_same_day_emails_nobody(self):
        send_due()
        self.assertEqual(send_due()["sent"], 0)
        self.assertEqual(len(mail.outbox), 2)

    def test_the_next_day_the_guardian_gets_a_fresh_link_and_the_student_no_second_email(self):
        send_due()
        self._a_day_later()

        self.assertEqual(send_due()["sent"], 1)

        self.assertEqual(len(self._to("pat@example.com")), 2)
        self.assertEqual(len(self._to("amy@example.com")), 1)
        first, second = GuardianConsentRequest.objects.filter(student=self.profile).order_by("pk")
        # Only the newest link works.
        self.assertIsNotNone(first.revoked_at)
        self.assertIsNone(second.revoked_at)

    def test_it_never_stops_until_consent_is_recorded(self):
        for _day in range(5):
            self.assertEqual(send_due()["sent"], 1)
            self._a_day_later()
        StudentProfile.objects.filter(pk=self.profile.pk).update(has_join_permission=True)

        self.assertEqual(send_due()["sent"], 0)
        self.assertEqual(len(self._to("pat@example.com")), 5)

    def test_who_is_due(self):
        # Due: an invited account, and a consented student whose change of
        # guardian waits on the new one.
        invited, _ = _student("ivy@example.com", account_status=User.AccountStatus.INVITED)
        changing, changing_profile = _student("cal@example.com", account_status=User.AccountStatus.ACTIVE)
        changing_profile.has_join_permission = True
        changing_profile.pending_pg_first_name = "Robin"
        changing_profile.pending_pg_last_name = "Carer"
        changing_profile.pending_pg_email = "robin@example.com"
        changing_profile.pending_pg_requested_at = timezone.now()
        changing_profile.save()
        # Not due: consent recorded, no guardian email, a suspended account,
        # last year's student, and one already emailed today.
        _, consented = _student("con@example.com")
        consented.has_join_permission = True
        consented.save()
        _student("none@example.com", guardian_email=None)
        _student("off@example.com", account_status=User.AccountStatus.SUSPENDED)
        _student("old@example.com", date_joined=timezone.now() - timedelta(days=400))
        _, today = _student("today@example.com")
        today.guardian_reminder_sent_at = timezone.now()
        today.save()

        due = {profile.user.email for profile in guardians_due()}

        self.assertEqual(due, {"amy@example.com", "ivy@example.com", "cal@example.com"})
        send_due()
        self.assertEqual(len(self._to("robin@example.com")), 1)

    def test_switching_it_off(self):
        with self.settings(GUARDIAN_REMINDER_INTERVAL_DAYS=0):
            self.assertTrue(send_due()["disabled"])
        SystemEmailTemplate.objects.create(key="guardian_consent_request", is_enabled=False)
        self.assertTrue(send_due()["disabled"])
        self.assertEqual(mail.outbox, [])

    def test_the_scheduler_needs_the_token(self):
        client = APIClient()
        url = reverse("guardian-consent-reminders")

        with self.settings(GUARDIAN_REMINDER_TOKEN=""):
            self.assertEqual(client.post(url).status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(client.post(url, HTTP_X_REMINDER_TOKEN="wrong").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(mail.outbox, [])

        response = client.post(url, HTTP_X_REMINDER_TOKEN="secret-token")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["sent"], 1)

    # -- a student naming their guardian ---------------------------------------

    def _as_student(self):
        RoleAssignmentHistory.objects.create(
            user=self.student, role=Roles.objects.get_or_create(role_name=ROLE_STUDENT)[0],
            valid_from=timezone.now() - timedelta(days=1),
        )
        client = APIClient()
        client.force_authenticate(self.student)
        return client

    def test_a_guardian_named_on_the_profile_is_emailed_at_once_and_only_once(self):
        client = self._as_student()
        details = {"first_name": "Robin", "last_name": "Carer", "email": "robin@example.com"}

        response = client.put(reverse("me-guardian"), details, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(self._to("robin@example.com")), 1)
        self.assertEqual(len(self._to("amy@example.com")), 1)
        # Saving the same guardian again doesn't email them again.
        client.put(reverse("me-guardian"), details, format="json")
        self.assertEqual(len(mail.outbox), 2)
        # The daily run leaves them until tomorrow.
        self.assertEqual(send_due()["sent"], 0)

    def test_a_new_guardian_named_after_consent_is_emailed_at_once(self):
        StudentProfile.objects.filter(pk=self.profile.pk).update(has_join_permission=True)
        client = self._as_student()

        client.put(
            reverse("me-guardian"),
            {"first_name": "Robin", "last_name": "Carer", "email": "robin@example.com"},
            format="json",
        )

        self.assertEqual(len(self._to("robin@example.com")), 1)
        self.assertEqual(self._to("pat@example.com"), [])
