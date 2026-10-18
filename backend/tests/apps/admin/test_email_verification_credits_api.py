"""GET /api/v1/admin/email-verification/credits/: each QuickEmailVerification
key's balance for admins (apps.admin.services.email_verification)."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.admin.services import email_verification as service
from apps.users import email_credits
from apps.users.models import AdminScope, EmailVerificationCredits

User = get_user_model()

FREE_KEY = "test-dummy-key"
PAID_KEY = "test-dummy-paid-key"
NOON = datetime(2026, 10, 18, 12, 0, tzinfo=dt_timezone.utc)

EMPTY_KEY = {
    "configured": True, "remaining": None, "updatedAt": None,
    "exhausted": False, "exhaustedAt": None, "retryAt": None,
}


@override_settings(
    QEV_API_KEY=FREE_KEY, QEV_PAID_API_KEY=PAID_KEY, QEV_LOW_CREDIT_THRESHOLDS=(500, 100),
    QEV_DAILY_LOOKUP_CAP=600, QEV_USE_SANDBOX=False, QEV_EXHAUSTED_RETRY_MINUTES=60,
)
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
            "free": EMPTY_KEY,
            "paid": {**EMPTY_KEY, "alertedThresholds": []},
            "thresholds": [500, 100], "lookupsToday": 0, "lookupsOn": None, "dailyCap": 600, "sandbox": False,
        })

    def test_reading_the_balance_never_creates_its_row(self):
        self.data()

        self.assertFalse(EmailVerificationCredits.objects.exists())

    def test_each_keys_balance_is_shown_and_alerts_only_for_the_paid_one(self):
        email_credits.record_remaining({email_credits.CREDITS_HEADER: "40"}, key="free")
        email_credits.record_remaining({email_credits.CREDITS_HEADER: "450"}, key="paid")
        credits = EmailVerificationCredits.objects.get()

        data = self.data()

        self.assertEqual((data["free"]["remaining"], data["free"]["updatedAt"]),
                         (40, credits.free_updated_at.isoformat()))
        self.assertEqual((data["paid"]["remaining"], data["paid"]["updatedAt"]),
                         (450, credits.updated_at.isoformat()))
        self.assertEqual(data["paid"]["alertedThresholds"], [500])
        self.assertNotIn("alertedThresholds", data["free"])

    def test_a_key_out_of_credit_shows_when_it_ran_out_and_when_its_tried_again(self):
        EmailVerificationCredits.objects.create(free_exhausted_at=NOON - timedelta(minutes=10))

        with mock.patch.object(service.timezone, "now", return_value=NOON):
            free = self.data()["free"]

        self.assertTrue(free["exhausted"])
        self.assertEqual(free["exhaustedAt"], (NOON - timedelta(minutes=10)).isoformat())
        self.assertEqual(free["retryAt"], (NOON + timedelta(minutes=50)).isoformat())

    def test_a_key_due_its_retry_is_no_longer_shown_as_out_of_credit(self):
        EmailVerificationCredits.objects.create(paid_exhausted_at=NOON - timedelta(minutes=61))

        with mock.patch.object(service.timezone, "now", return_value=NOON):
            paid = self.data()["paid"]

        self.assertFalse(paid["exhausted"])
        self.assertEqual(paid["exhaustedAt"], (NOON - timedelta(minutes=61)).isoformat())

    @override_settings(QEV_PAID_API_KEY="")
    def test_whether_each_key_is_set_is_shown_but_never_the_key(self):
        response = self.get(self.admin)
        data = response.json()["data"]

        self.assertEqual((data["free"]["configured"], data["paid"]["configured"]), (True, False))
        self.assertNotIn(FREE_KEY, response.content.decode())

    def test_neither_key_appears_in_the_response(self):
        email_credits.record_remaining({email_credits.CREDITS_HEADER: "40"}, key="free")
        EmailVerificationCredits.objects.filter(pk=1).update(paid_exhausted_at=timezone.now())

        body = self.get(self.admin).content.decode()

        self.assertNotIn(FREE_KEY, body)
        self.assertNotIn(PAID_KEY, body)

    def test_todays_lookups_and_a_count_from_an_earlier_day(self):
        EmailVerificationCredits.objects.create(lookups_on=timezone.now().date(), lookups_today=37)
        self.assertEqual(self.data()["lookupsToday"], 37)

        yesterday = timezone.now().date() - timedelta(days=1)
        EmailVerificationCredits.objects.filter(pk=1).update(lookups_on=yesterday)
        data = self.data()
        self.assertEqual((data["lookupsToday"], data["lookupsOn"]), (0, yesterday.isoformat()))

    @override_settings(QEV_LOW_CREDIT_THRESHOLDS=(100, 1000, 100), QEV_DAILY_LOOKUP_CAP=50, QEV_USE_SANDBOX=True)
    def test_the_levels_cap_and_sandbox_come_from_the_settings(self):
        data = self.data()

        self.assertEqual((data["thresholds"], data["dailyCap"], data["sandbox"]), ([1000, 100], 50, True))

    def test_with_the_cap_setting_missing_it_reports_no_limit(self):
        from django.conf import settings

        with override_settings():
            del settings.QEV_DAILY_LOOKUP_CAP
            self.assertEqual(self.data()["dailyCap"], 0)

    def test_it_is_read_only(self):
        self.client.force_authenticate(self.admin)

        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url, {"remaining": 9999}, format="json")
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertFalse(EmailVerificationCredits.objects.exists())
