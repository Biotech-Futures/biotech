"""Tests for guardian consent signed on the platform.

The public page's API (load the form behind a link, sign it), which links stop
working and why, what a signature must be, what signing records, and the admin
side: viewing signed consents, recording withdrawals and the media-consent flag
on event RSVPs.
"""
import base64
import io
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image, ImageDraw
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.common.storage import get_consent_storage, reset_managed_storage_caches
from apps.events.models import EventRsvp, Events
from apps.users import guardian_consent
from apps.users.consent_form import CURRENT_VERSION
from apps.users.models import GuardianConsent, StudentProfile, User
from apps.users.models.admin_scope import AdminScope

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def png_data_url(drawn: bool = True) -> str:
    image = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    if drawn:
        ImageDraw.Draw(image).line([(20, 70), (120, 20), (260, 80)], fill=(0, 0, 0, 255), width=4)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def make_student(email="wren@example.com", first="Wren", **profile):
    user = User.objects.create_user(email=email, password="x", first_name=first, last_name="Ward")
    defaults = dict(
        pg_first_name="Pat", pg_last_name="Parent", pg_email="pat@example.com",
        parent_guardian_flag=True, school_name="Test High", year_lvl="10",
    )
    defaults.update(profile)
    return StudentProfile.objects.create(user=user, **defaults)


class TempMediaMixin:
    """Signing stores a PDF; keep it in a throwaway folder."""

    def use_temp_media(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        setting = override_settings(MEDIA_ROOT=media.name)
        setting.enable()
        self.addCleanup(setting.disable)
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)


def issue(profile):
    _, token = guardian_consent.issue_request(profile, guardian_consent.guardian_to_ask(profile))
    return token


@override_settings(EMAIL_BACKEND=LOCMEM)
class ConsentPageTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.use_temp_media()
        self.client = APIClient()
        self.profile = make_student()
        self.token = issue(self.profile)

    def url(self, token=None):
        return f"/api/v1/consent/{token or self.token}/"

    def sign(self, token=None, **overrides):
        body = {
            "guardianFullName": "Pat Parent",
            "mediaConsent": True,
            "signature": png_data_url(),
            "agreed": True,
            "consentVersion": CURRENT_VERSION,
            **overrides,
        }
        return self.client.post(self.url(token), body, format="json")

    # -- loading the form ----------------------------------------------------

    def test_loads_the_form_for_a_valid_link(self):
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["studentName"], "Wren Ward")
        self.assertEqual(response.data["guardianFirstName"], "Pat")
        form = response.data["form"]
        self.assertEqual(form["version"], CURRENT_VERSION)
        self.assertIn("Wren Ward", form["body_html"])
        self.assertIn("support@biotechfutures.org", form["body_html"])
        self.assertIn("Wren Ward may attend in-person", form["media_yes"])
        self.assertIn("will not be permitted", form["media_no"])

    def test_student_name_is_escaped_in_the_form(self):
        profile = make_student(email="x@example.com", first="<b>Evil</b>", pg_email="g@example.com")
        response = self.client.get(self.url(issue(profile)))

        self.assertNotIn("<b>Evil</b>", response.data["form"]["body_html"])
        self.assertIn("&lt;b&gt;Evil&lt;/b&gt;", response.data["form"]["body_html"])

    def test_unknown_link_is_404(self):
        self.assertEqual(self.client.get(self.url("nope")).status_code, status.HTTP_404_NOT_FOUND)

    def test_expired_link_is_gone(self):
        self.profile.consent_requests.update(expires_at=timezone.now() - timedelta(minutes=1))

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data["code"], "consent_link_expired")

    def test_link_stops_working_when_the_guardian_changes(self):
        self.profile.pg_email = "someone.else@example.com"
        self.profile.save()

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data["code"], "consent_link_out_of_date")

    # -- signing ---------------------------------------------------------------

    def test_signing_records_consent_and_emails_a_copy(self):
        response = self.sign(mediaConsent=False)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        consent = GuardianConsent.objects.get(student=self.profile)
        self.assertEqual(response.data["reference"], consent.reference)
        self.assertEqual(consent.guardian_full_name, "Pat Parent")
        self.assertEqual(consent.guardian_email, "pat@example.com")
        self.assertFalse(consent.media_consent)
        self.assertEqual(consent.consent_version, CURRENT_VERSION)
        self.assertTrue(bytes(consent.signature_png).startswith(b"\x89PNG"))

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_join_permission)
        self.assertEqual(self.profile.joinperm_responseID, consent.reference)
        self.assertIsNotNone(self.profile.joinperm_granted_at)
        self.assertIs(self.profile.media_consent, False)
        self.assertIsNotNone(consent.request.used_at)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["pat@example.com"])
        self.assertIn(consent.reference, mail.outbox[0].alternatives[0][0])
        self.assertIn("No, media consent not provided", mail.outbox[0].alternatives[0][0])
        self.assertTrue(AuditLog.objects.filter(action="guardian_consent_signed").exists())

    def test_signing_stores_the_record_pdf_and_attaches_it(self):
        self.sign()

        consent = GuardianConsent.objects.get()
        self.assertEqual(consent.record_pdf_key, f"{self.profile.user_id}/{consent.reference}.pdf")
        with get_consent_storage().open(consent.record_pdf_key) as stored:
            self.assertTrue(stored.read().startswith(b"%PDF"))
        [(filename, content, mimetype)] = mail.outbox[0].attachments[1:]  # [0] is the inline logo
        self.assertEqual(mimetype, "application/pdf")
        self.assertTrue(filename.startswith(consent.reference))
        self.assertTrue(content.startswith(b"%PDF"))

    def test_storage_failure_does_not_stop_signing(self):
        with patch("apps.common.storage.ManagedContainerStorage.save", side_effect=OSError("down")):
            response = self.sign()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        consent = GuardianConsent.objects.get()
        self.assertEqual(consent.record_pdf_key, "")
        self.assertEqual(len(mail.outbox), 1)  # still sent, with the PDF

    def test_record_renders_names_outside_western_scripts(self):
        profile = make_student(email="li@example.com", first="李", pg_email="g3@example.com")

        response = self.sign(issue(profile), guardianFullName="王 芳")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_a_link_signs_once(self):
        self.sign()

        response = self.sign()

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data["code"], "consent_link_used")
        self.assertEqual(GuardianConsent.objects.count(), 1)

    def test_signing_for_a_guardian_change_makes_them_the_guardian(self):
        self.profile.has_join_permission = True
        self.profile.joinperm_responseID = "R_old"
        self.profile.pending_pg_first_name = "Sam"
        self.profile.pending_pg_last_name = "Step"
        self.profile.pending_pg_email = "sam@example.com"
        self.profile.pending_pg_requested_at = timezone.now()
        self.profile.save()
        token = issue(self.profile)

        response = self.sign(token, guardianFullName="Sam Step")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.pg_email, "sam@example.com")
        self.assertEqual(self.profile.pg_first_name, "Sam")
        self.assertFalse(self.profile.has_pending_guardian)
        self.assertTrue(self.profile.joinperm_responseID.startswith("BTF-"))

    def test_incomplete_forms_are_refused(self):
        cases = {
            "blank signature": {"signature": png_data_url(drawn=False)},
            "not an image": {"signature": "data:image/png;base64,aGVsbG8="},
            "not a png data url": {"signature": "hello"},
            "no name": {"guardianFullName": "   "},
            "not agreed": {"agreed": False},
            "old wording": {"consentVersion": "2020-01-01"},
            "no media answer": {"mediaConsent": None},
        }
        for label, overrides in cases.items():
            with self.subTest(label):
                response = self.sign(**overrides)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(GuardianConsent.objects.exists())
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.has_join_permission)


@override_settings(EMAIL_BACKEND=LOCMEM)
class AdminConsentTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.use_temp_media()
        self.admin = User.objects.create_user(email="admin@example.com", password="x")
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.profile = make_student()
        guardian_consent.sign(
            issue(self.profile), full_name="Pat Parent", media_consent=True,
            signature=png_data_url(), version=CURRENT_VERSION, ip="203.0.113.7", user_agent="test",
        )
        self.base = f"/api/v1/admin/user/{self.profile.user_id}"

    def test_lists_signed_consents_with_the_signature(self):
        response = self.client.get(f"{self.base}/guardian-consents/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        [item] = response.data["data"]
        self.assertEqual(item["guardianFullName"], "Pat Parent")
        self.assertTrue(item["mediaConsent"])
        self.assertTrue(item["signature"].startswith("data:image/png;base64,"))

    def test_admin_payload_shows_media_consent(self):
        response = self.client.get(f"{self.base}/")

        self.assertIs(response.data["data"]["mediaConsent"], True)
        self.assertEqual(response.data["data"]["joinpermResponseId"][:4], "BTF-")

    def test_downloads_the_signed_record(self):
        consent = GuardianConsent.objects.get()

        response = self.client.get(f"{self.base}/guardian-consents/{consent.pk}/record/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(f'filename="{consent.reference}', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_rebuilds_a_missing_record(self):
        consent = GuardianConsent.objects.get()
        get_consent_storage().delete(consent.record_pdf_key)

        response = self.client.get(f"{self.base}/guardian-consents/{consent.pk}/record/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.content.startswith(b"%PDF"))
        consent.refresh_from_db()
        self.assertTrue(get_consent_storage().exists(consent.record_pdf_key))

    def test_record_belongs_to_its_student(self):
        consent = GuardianConsent.objects.get()
        other = make_student(email="other2@example.com", pg_email="g4@example.com")

        response = self.client.get(f"/api/v1/admin/user/{other.user_id}/guardian-consents/{consent.pk}/record/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_withdrawing_media_consent_keeps_participation(self):
        response = self.client.post(f"{self.base}/guardian-consent-withdrawal/", {"mediaOnly": True}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_join_permission)
        self.assertIs(self.profile.media_consent, False)
        self.assertIsNotNone(GuardianConsent.objects.get().media_withdrawn_at)
        self.assertTrue(
            AuditLog.objects.filter(action="guardian_media_consent_withdrawn", actor_user=self.admin).exists()
        )

    def test_withdrawing_consent_ends_participation_and_allows_a_new_request(self):
        response = self.client.post(f"{self.base}/guardian-consent-withdrawal/", {"mediaOnly": False}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.has_join_permission)
        self.assertIsNone(self.profile.joinperm_responseID)
        self.assertIsNone(self.profile.media_consent)
        self.assertIsNotNone(GuardianConsent.objects.get().withdrawn_at)
        self.assertEqual(guardian_consent.guardian_to_ask(self.profile).email, "pat@example.com")

    def test_cannot_withdraw_without_consent(self):
        other = make_student(email="other@example.com", pg_email="g@example.com")

        response = self.client.post(
            f"/api/v1/admin/user/{other.user_id}/guardian-consent-withdrawal/", {"mediaOnly": False}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rsvps_flag_students_without_media_consent_on_in_person_events(self):
        no_media = make_student(email="nomedia@example.com", pg_email="g2@example.com", media_consent=False)
        start = timezone.now() + timedelta(days=2)
        in_person = Events.objects.create(
            event_name="Lab visit", start_datetime=start, ends_datetime=start + timedelta(hours=2),
            event_format="in_person",
        )
        virtual = Events.objects.create(
            event_name="Webinar", start_datetime=start, ends_datetime=start + timedelta(hours=2),
            event_format="virtual",
        )
        for event in (in_person, virtual):
            for profile in (self.profile, no_media):
                EventRsvp.objects.create(event=event, user=profile.user, rsvp_status="accepted")

        flags = {
            event.event_name: {
                r["userId"]: r["noMediaConsent"]
                for r in self.client.get(f"/api/v1/admin/event/{event.id}/rsvp/").data["data"]
            }
            for event in (in_person, virtual)
        }

        self.assertEqual(flags["Lab visit"], {self.profile.user_id: False, no_media.user_id: True})
        self.assertEqual(flags["Webinar"], {self.profile.user_id: False, no_media.user_id: False})
