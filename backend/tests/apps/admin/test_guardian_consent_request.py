"""Tests for the admin "Send consent request" button.

Pins who the email goes to (a requested guardian change before the guardian on
file), when it refuses (consent already in, no address, no form link, switched
off, sent moments ago), and that a failed send isn't recorded as sent.
"""
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.services.models import SystemEmailTemplate
from apps.users.models import StudentProfile, User
from apps.users.models.admin_scope import AdminScope

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
FORM_URL = "https://forms.example.com/consent"


@override_settings(EMAIL_BACKEND=LOCMEM, GUARDIAN_CONSENT_FORM_URL=FORM_URL)
class GuardianConsentRequestTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="x", first_name="Ada", last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

        self.student = User.objects.create_user(
            email="wren@example.com", password="x", first_name="Wren", last_name="Ward",
        )
        self.profile = StudentProfile.objects.create(
            user=self.student,
            pg_first_name="Pat",
            pg_last_name="Parent",
            pg_email="pat@example.com",
            parent_guardian_flag=True,
            school_name="Test High",
            year_lvl="10",
        )

    def _post(self, user_id=None):
        return self.client.post(
            f"/api/v1/admin/user/{user_id or self.student.id}/guardian-consent-request/"
        )

    def test_sends_to_guardian_with_form_link_and_student_email(self):
        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["pat@example.com"])
        self.assertIn("Wren", message.subject)
        html = message.alternatives[0][0]
        self.assertIn(FORM_URL, html)
        self.assertIn("wren@example.com", html)
        self.assertIn("Hi Pat", html)

        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.guardian_request_sent_at)
        self.assertEqual(
            response.data["data"]["consentRequestSentAt"],
            self.profile.guardian_request_sent_at.isoformat(),
        )
        self.assertTrue(
            AuditLog.objects.filter(
                entity_id=self.student.id, action="guardian_consent_request", actor_user=self.admin,
            ).exists()
        )

    def test_placeholder_guardian_name_is_not_used_as_greeting(self):
        self.profile.pg_first_name, self.profile.pg_last_name = "Wren", "Ward"
        self.profile.save()

        self._post()

        html = mail.outbox[0].alternatives[0][0]
        self.assertNotIn("Hi Wren", html)
        self.assertIn("Hi there", html)

    def test_pending_guardian_change_goes_to_the_new_guardian(self):
        self.profile.has_join_permission = True
        self.profile.joinperm_responseID = "R_1"
        self.profile.pending_pg_first_name = "Sam"
        self.profile.pending_pg_last_name = "Step"
        self.profile.pending_pg_email = "sam@example.com"
        self.profile.pending_pg_requested_at = timezone.now()
        self.profile.save()

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(mail.outbox[0].to, ["sam@example.com"])

    def test_refuses_when_consent_already_recorded(self):
        self.profile.has_join_permission = True
        self.profile.joinperm_responseID = "R_1"
        self.profile.save()

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(mail.outbox, [])

    def test_refuses_without_a_guardian_email(self):
        self.profile.pg_email = None
        self.profile.save()

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(mail.outbox, [])

    @override_settings(GUARDIAN_CONSENT_FORM_URL="")
    def test_refuses_without_a_form_link(self):
        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(mail.outbox, [])

    def test_refuses_when_switched_off(self):
        SystemEmailTemplate.objects.create(key="guardian_consent_request", is_enabled=False)

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(mail.outbox, [])
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.guardian_request_sent_at)

    def test_resend_waits_for_cooldown(self):
        self.assertEqual(self._post().status_code, status.HTTP_200_OK)
        self.assertEqual(self._post().status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(len(mail.outbox), 1)

        StudentProfile.objects.filter(pk=self.profile.pk).update(
            guardian_request_sent_at=timezone.now() - timedelta(minutes=11),
        )
        self.assertEqual(self._post().status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)

    def test_failed_send_is_not_recorded(self):
        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("down")):
            response = self._post()

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.guardian_request_sent_at)

    def test_unknown_student_is_404(self):
        self.assertEqual(self._post(user_id=999999).status_code, status.HTTP_404_NOT_FOUND)

    def test_non_admin_is_refused(self):
        client = APIClient()
        client.force_authenticate(self.student)

        response = client.post(f"/api/v1/admin/user/{self.student.id}/guardian-consent-request/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(mail.outbox, [])
