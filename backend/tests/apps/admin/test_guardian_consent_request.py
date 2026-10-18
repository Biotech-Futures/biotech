"""Tests for the admin "Send consent request" button.

Pins who the email goes to (a requested guardian change before the guardian on
file), when it refuses (consent already in, no address, the student's own
address, switched off, sent moments ago), that the emailed link opens the
platform's consent page, that a failed send leaves no working link, and that
the student is told their guardian was sent the form.
"""
import re
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.services.models import SystemEmailTemplate
from apps.services.system_email import FAILED, send_system_email
from apps.users.models import GuardianConsentRequest, StudentProfile, User
from apps.users.models.admin_scope import AdminScope

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
FRONTEND = "https://connect.example.com"
LINK_RE = re.compile(re.escape(FRONTEND) + r"/#/consent/([A-Za-z0-9_-]+)")


@override_settings(EMAIL_BACKEND=LOCMEM, FRONTEND_BASE_URL=FRONTEND)
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

    def _link_token(self, message):
        match = LINK_RE.search(message.alternatives[0][0])
        self.assertIsNotNone(match, "no consent link in the email")
        return match.group(1)

    def _to(self, address):
        return [message for message in mail.outbox if message.to == [address]]

    def test_sends_guardian_a_link_to_the_consent_page(self):
        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The guardian's request, then the student's notice.
        self.assertEqual([m.to for m in mail.outbox], [["pat@example.com"], ["wren@example.com"]])
        message = mail.outbox[0]
        # The client's wording: subject, student named in the body, its button.
        self.assertEqual(message.subject, "Action Required: Sign parent/guardian permission form")
        html = message.alternatives[0][0]
        self.assertIn("Hi Pat", html)
        self.assertIn("Wren Ward recently registered for the BIOTech Futures Challenge", html)
        self.assertIn("to enable Wren to participate", html)
        self.assertIn("Action Permission Request", html)
        self.assertIn("mailto:info@biotechfutures.org", html)

        token = self._link_token(message)
        request = GuardianConsentRequest.objects.get(student=self.profile)
        self.assertNotEqual(request.token_hash, token)  # only a hash is stored
        self.assertEqual(request.guardian_email, "pat@example.com")
        self.assertEqual(request.sent_by, self.admin)
        self.assertEqual(self.client.get(f"/api/v1/consent/{token}/").status_code, status.HTTP_200_OK)

        self.assertEqual(
            response.data["data"]["consentRequestSentAt"], request.created_at.isoformat(),
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
        self.assertTrue(GuardianConsentRequest.objects.get(student=self.profile).for_pending_guardian)
        # The student's notice names the guardian the form went to.
        self.assertIn("sam@example.com", self._to("wren@example.com")[0].alternatives[0][0])

    def test_student_is_told_their_guardian_was_sent_the_form(self):
        self._post()

        notices = self._to("wren@example.com")
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].subject, "Parent/Guardian Action Required - Permission Form")
        html = notices[0].alternatives[0][0]
        self.assertIn("Hi Wren", html)
        self.assertIn("has just now been sent a permission form to", html)
        self.assertIn("pat@example.com", html)
        self.assertIn("Please remind them to complete it as soon as possible.", html)
        self.assertIn("You will not be able to participate in BIOTech Futures unless this step is completed.", html)
        # The consent link is the guardian's alone.
        self.assertIsNone(LINK_RE.search(html))

    def test_student_notice_switched_off_still_sends_the_request(self):
        SystemEmailTemplate.objects.create(key="guardian_consent_student_notice", is_enabled=False)

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([m.to for m in mail.outbox], [["pat@example.com"]])
        self.assertEqual(GuardianConsentRequest.objects.count(), 1)

    def test_failed_student_notice_keeps_the_request(self):
        def send(key, *args, **kwargs):
            if key == "guardian_consent_student_notice":
                return FAILED
            return send_system_email(key, *args, **kwargs)

        with patch("apps.admin.services.guardian_consent.send_system_email", side_effect=send):
            response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([m.to for m in mail.outbox], [["pat@example.com"]])
        self.assertEqual(GuardianConsentRequest.objects.count(), 1)

    def test_resending_replaces_the_earlier_link(self):
        self._post()
        first = self._link_token(self._to("pat@example.com")[0])
        GuardianConsentRequest.objects.update(created_at=timezone.now() - timedelta(minutes=11))

        self._post()
        second = self._link_token(self._to("pat@example.com")[1])

        self.assertEqual(self.client.get(f"/api/v1/consent/{first}/").status_code, status.HTTP_410_GONE)
        self.assertEqual(self.client.get(f"/api/v1/consent/{second}/").status_code, status.HTTP_200_OK)

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

    def test_refuses_when_guardian_email_is_the_students_own(self):
        self.profile.pg_email = "Wren@Example.com"
        self.profile.save()

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("student's own address", response.data["msg"])
        self.assertEqual(mail.outbox, [])

    def test_refuses_when_switched_off_and_leaves_no_link(self):
        SystemEmailTemplate.objects.create(key="guardian_consent_request", is_enabled=False)

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(GuardianConsentRequest.objects.exists())

    def test_resend_waits_for_cooldown(self):
        self.assertEqual(self._post().status_code, status.HTTP_200_OK)
        self.assertEqual(self._post().status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(len(self._to("pat@example.com")), 1)

        GuardianConsentRequest.objects.update(created_at=timezone.now() - timedelta(minutes=11))
        self.assertEqual(self._post().status_code, status.HTTP_200_OK)
        self.assertEqual(len(self._to("pat@example.com")), 2)

    def test_failed_send_leaves_the_previous_link_working(self):
        self._post()
        first = self._link_token(mail.outbox[0])
        GuardianConsentRequest.objects.update(created_at=timezone.now() - timedelta(minutes=11))

        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("down")):
            response = self._post()

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(GuardianConsentRequest.objects.count(), 1)
        self.assertEqual(self.client.get(f"/api/v1/consent/{first}/").status_code, status.HTTP_200_OK)

    def test_unknown_student_is_404(self):
        self.assertEqual(self._post(user_id=999999).status_code, status.HTTP_404_NOT_FOUND)

    def test_non_admin_is_refused(self):
        client = APIClient()
        client.force_authenticate(self.student)

        response = client.post(f"/api/v1/admin/user/{self.student.id}/guardian-consent-request/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(mail.outbox, [])
