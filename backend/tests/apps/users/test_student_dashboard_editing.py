from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.groups.models import Countries, CountryStates, Groups, GroupMembership
from apps.groups.serializers import GroupMembershipSerializer
from apps.users.models import User, StudentProfile, SupervisorProfile, AreasOfInterest, UserInterest


@override_settings(FRONTEND_BASE_URL="http://localhost:5173", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", GUARDIAN_REMINDER_INTERVAL_DAYS=0)
class StudentDashboardEditingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="student@example.org", first_name="Hiro", last_name="Bianchi", account_status="active")
        self.profile = StudentProfile.objects.create(
            user=self.user, pg_first_name="Pat", pg_last_name="Bianchi", pg_email=None,
            school_name="Test High", year_lvl="10", parent_guardian_flag=True,
            has_join_permission=True, joinperm_responseID="old-response", joinperm_granted_at=timezone.now(),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse("MeListHTMLView")

    def test_blank_email_does_not_clear_existing_consent(self):
        previous = self.profile.joinperm_granted_at
        response = self.client.patch(self.url, {"school_name": "New High", "pg_email": ""}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_join_permission)
        self.assertEqual(self.profile.joinperm_granted_at, previous)

    def test_real_guardian_change_clears_consent_and_old_reminders(self):
        self.profile.guardian_reminder_sent_at = timezone.now()
        self.profile.guardian_reminder_due_at = timezone.now()
        self.profile.save()
        response = self.client.patch(self.url, {"pg_email": "newguardian@example.org"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.has_join_permission)
        for field in ("joinperm_granted_at", "joinperm_responseID", "guardian_reminder_sent_at", "guardian_reminder_due_at"):
            self.assertIsNone(getattr(self.profile, field))

    def test_geography_and_interest_edits(self):
        country = Countries.objects.create(country_name="Australia")
        region = CountryStates.objects.create(country=country, state_name="NSW")
        interest = AreasOfInterest.objects.create(interest_desc="Biology")
        response = self.client.patch(self.url, {"country_id": country.pk, "state_id": region.pk, "interest_ids": [interest.pk]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.state, region)
        self.assertEqual(response.data["interests"], ["Biology"])
        self.assertTrue(UserInterest.objects.filter(user=self.user, interest=interest).exists())
        response = self.client.patch(self.url, {"interest_ids": []}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserInterest.objects.filter(user=self.user).exists())

    def test_mismatched_region_rejects_entire_update(self):
        country = Countries.objects.create(country_name="Australia")
        region = CountryStates.objects.create(country=country, state_name="NSW")
        response = self.client.patch(self.url, {"country_id": None, "state_id": region.pk, "first_name": "Changed"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Hiro")

    def test_supervisor_managed_profile_cannot_edit(self):
        supervisor = User.objects.create_user(email="supervisor@example.org")
        self.profile.supervisor = SupervisorProfile.objects.create(user=supervisor, school_name="Test High")
        self.profile.save()
        response = self.client.patch(self.url, {"interest_ids": [], "first_name": "Changed"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Hiro")

    def _to(self, address):
        return [message for message in mail.outbox if message.to == [address]]

    def prepare_invitation(self):
        self.profile.has_join_permission = False
        self.profile.pg_email = "guardian@example.org"
        self.profile.save()

    def test_invitation_sends_to_saved_guardian_and_tracks_success(self):
        self.prepare_invitation()
        response = self.client.post(reverse("guardian-invitation"), {"email": "other@example.org"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(mail.outbox[0].to, ["guardian@example.org"])
        self.assertIn("http://localhost:5173/#/consent/", mail.outbox[0].body)
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.guardian_reminder_sent_at)
        self.assertIsNone(self.profile.guardian_reminder_due_at)
        response = self.client.post(reverse("guardian-invitation"), {}, format="json")
        self.assertEqual(response.status_code, 429)
        # The guardian's request once, and the student told once that it went.
        self.assertEqual(len(self._to("guardian@example.org")), 1)
        self.assertEqual(len(self._to("student@example.org")), 1)

    def test_missing_guardian_email_cannot_send(self):
        self.prepare_invitation()
        self.profile.pg_email = None
        self.profile.save()
        response = self.client.post(reverse("guardian-invitation"), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.guardian_reminder_sent_at)

    def test_pending_guardian_invitation_preserves_current_consent(self):
        self.profile.pg_email = "currentguardian@example.org"
        self.profile.pending_pg_first_name = "New"
        self.profile.pending_pg_last_name = "Guardian"
        self.profile.pending_pg_email = "newguardian@example.org"
        self.profile.pending_pg_requested_at = timezone.now()
        self.profile.save()
        response = self.client.post(reverse("guardian-invitation"), {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(mail.outbox[0].to, ["newguardian@example.org"])
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_join_permission)
        self.assertEqual(self.profile.pg_email, "currentguardian@example.org")
        self.assertTrue(self.profile.consent_requests.get().for_pending_guardian)

    @patch("apps.admin.services.guardian_consent.send_system_email", return_value="failed")
    def test_failed_delivery_does_not_record_sent(self, send):
        self.prepare_invitation()
        response = self.client.post(reverse("guardian-invitation"), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.guardian_reminder_sent_at)

    @override_settings(GUARDIAN_REMINDER_INTERVAL_DAYS=7)
    def test_scheduled_reminder_sends_only_when_due(self):
        self.prepare_invitation()
        self.profile.guardian_reminder_due_at = timezone.now() - timedelta(days=1)
        self.profile.save()
        call_command("send_guardian_reminders")
        self.profile.refresh_from_db()
        self.assertGreater(self.profile.guardian_reminder_due_at, timezone.now())
        # The guardian's request, and the student told that it went.
        self.assertEqual(len(self._to("guardian@example.org")), 1)
        self.assertEqual(len(self._to("student@example.org")), 1)
        call_command("send_guardian_reminders")
        self.assertEqual(len(mail.outbox), 2)

    def test_team_details_do_not_expose_guardian_data(self):
        group = Groups.objects.create(group_name="Team Test", year=2026)
        member = GroupMembership.objects.create(group=group, user=self.user, membership_role="student")
        details = GroupMembershipSerializer(member).data["student_details"]
        self.assertEqual(details, {"first_name": "Hiro", "last_name": "Bianchi", "school": "Test High", "year_level": "10", "supervisor": None})

    def test_unauthenticated_invitation_denied(self):
        self.client.force_authenticate(None)
        response = self.client.post(reverse("guardian-invitation"), {}, format="json")
        self.assertIn(response.status_code, [401, 403])
