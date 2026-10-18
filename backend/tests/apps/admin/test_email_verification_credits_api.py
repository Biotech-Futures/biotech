"""GET /api/v1/admin/email-verification/credits/: the QuickEmailVerification
balance for admins (apps.admin.services.email_verification)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users import email_credits
from apps.users.models import AdminScope, EmailVerificationCredits

User = get_user_model()


@override_settings(QEV_LOW_CREDIT_THRESHOLDS=(500, 100), QEV_DAILY_LOOKUP_CAP=600, QEV_USE_SANDBOX=False)
class EmailVerificationCreditsApiTests(APITestCase):
    url = "/api/v1/admin/email-verification/credits/"

    def setUp(self):
        self.admin = User.objects.create_user(email="credits.admin@example.com")
        AdminScope.objects.create(user=self.admin)

    def get(self, user=None):
        if user is not None:
            self.client.force_authenticate(user)
        return self.client.get(self.url)

    def data(self):
        response = self.get(self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()["msg"], "Email verification credits retrieved successfully")
        return response.json()["data"]

    def test_anonymous_and_non_admin_users_are_refused(self):
        self.assertEqual(self.get().status_code, status.HTTP_403_FORBIDDEN)
        for user in (
            User.objects.create_user(email="student@example.com"),
            User.objects.create_user(email="staff@example.com", is_staff=True),
        ):
            with self.subTest(user=user.email):
                self.assertEqual(self.get(user).status_code, status.HTTP_403_FORBIDDEN)

    def test_before_any_balance_is_reported_everything_is_empty(self):
        self.assertEqual(self.data(), {
            "remaining": None, "updatedAt": None, "alertedThresholds": [], "thresholds": [500, 100],
            "lookupsToday": 0, "lookupsOn": None, "dailyCap": 600, "sandbox": False,
        })

    def test_reading_the_balance_never_creates_its_row(self):
        self.data()

        self.assertFalse(EmailVerificationCredits.objects.exists())

    def test_after_a_reading_it_shows_the_balance_and_the_alerts_sent(self):
        email_credits.record_remaining({email_credits.CREDITS_HEADER: "450"})
        credits = EmailVerificationCredits.objects.get()
        credits.lookups_on, credits.lookups_today = timezone.now().date(), 37
        credits.save()

        data = self.data()

        self.assertEqual(data["remaining"], 450)
        self.assertEqual(data["updatedAt"], credits.updated_at.isoformat())
        self.assertEqual(data["alertedThresholds"], [500])
        self.assertEqual((data["lookupsToday"], data["lookupsOn"]), (37, timezone.now().date().isoformat()))

    def test_a_count_from_an_earlier_day_isnt_today(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        EmailVerificationCredits.objects.create(remaining=2000, lookups_on=yesterday, lookups_today=600)

        data = self.data()

        self.assertEqual((data["lookupsToday"], data["lookupsOn"]), (0, yesterday.isoformat()))

    @override_settings(QEV_LOW_CREDIT_THRESHOLDS=(100, 1000, 100), QEV_DAILY_LOOKUP_CAP=50, QEV_USE_SANDBOX=True)
    def test_the_levels_cap_and_sandbox_come_from_the_settings(self):
        data = self.data()

        self.assertEqual((data["thresholds"], data["dailyCap"], data["sandbox"]), ([1000, 100], 50, True))

    def test_it_is_read_only(self):
        self.client.force_authenticate(self.admin)

        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url, {"remaining": 9999}, format="json")
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertFalse(EmailVerificationCredits.objects.exists())
