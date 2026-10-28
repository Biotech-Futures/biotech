"""GET /api/v1/admin/email-verification/requests/: QuickEmailVerification
requests and credits by UTC day, key and outcome, for Team 4's dashboard
(apps.admin.services.email_requests)."""
from datetime import date, datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.admin.services.email_requests import RangeError, usage_range
from apps.users.models import AdminScope, EmailVerificationRequest

User = get_user_model()


def at(day, hour, key, outcome, credits=1):
    row = EmailVerificationRequest.objects.create(key=key, outcome=outcome, credits=credits)
    EmailVerificationRequest.objects.filter(pk=row.pk).update(
        requested_at=datetime(2026, 10, day, hour, 30, tzinfo=dt_timezone.utc)
    )


class EmailVerificationRequestsApiTests(APITestCase):
    url = "/api/v1/admin/email-verification/requests/"

    def setUp(self):
        self.admin = User.objects.create_user(email="usage.admin@example.com")
        AdminScope.objects.create(user=self.admin)
        # The 27th: two free answers, a free key out of credit then the paid
        # key's answer, and a timeout. The 28th: one paid answer, just after
        # midnight UTC. The 20th: before the range asked for.
        at(27, 1, "free", "valid")
        at(27, 2, "free", "valid")
        at(27, 3, "free", "out_of_credit", credits=0)
        at(27, 3, "paid", "invalid")
        at(27, 23, "paid", "request_timeout", credits=0)
        at(28, 0, "paid", "valid")
        at(20, 9, "free", "valid")

    def get(self, query="", user=None):
        self.client.force_authenticate(user or self.admin)
        return self.client.get(self.url + query)

    def test_requests_and_credits_by_day_key_and_outcome(self):
        response = self.get("?from=2026-10-27&to=2026-10-28")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()["msg"], "Email verification requests retrieved successfully")
        data = response.json()["data"]
        self.assertEqual((data["from"], data["to"], data["timezone"]), ("2026-10-27", "2026-10-28", "UTC"))
        self.assertEqual(data["days"], [
            {"date": "2026-10-27", "key": "free", "outcome": "out_of_credit", "requests": 1, "credits": 0},
            {"date": "2026-10-27", "key": "free", "outcome": "valid", "requests": 2, "credits": 2},
            {"date": "2026-10-27", "key": "paid", "outcome": "invalid", "requests": 1, "credits": 1},
            {"date": "2026-10-27", "key": "paid", "outcome": "request_timeout", "requests": 1, "credits": 0},
            {"date": "2026-10-28", "key": "paid", "outcome": "valid", "requests": 1, "credits": 1},
        ])
        self.assertEqual(data["totals"], {"requests": 6, "credits": 4})

    def test_an_empty_range_answers_with_nothing(self):
        data = self.get("?from=2026-09-01&to=2026-09-30").json()["data"]
        self.assertEqual((data["days"], data["totals"]), ([], {"requests": 0, "credits": 0}))

    def test_a_bad_range_is_refused(self):
        for query, message in (
            ("?from=yesterday", "from must be a date like 2026-10-28."),
            ("?from=2026-10-28&to=2026-10-27", "from must be on or before to."),
            ("?from=2025-01-01&to=2026-10-28", "Ask for at most 366 days at a time."),
        ):
            with self.subTest(query=query):
                response = self.get(query)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.json()["detail"], message)

    def test_anonymous_and_non_admin_users_are_refused(self):
        self.assertIn(self.client.get(self.url).status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        member = User.objects.create_user(email="not.admin@example.com")
        self.assertEqual(self.get(user=member).status_code, status.HTTP_403_FORBIDDEN)


class UsageRangeTests(APITestCase):
    def test_the_last_30_days_up_to_today_by_default(self):
        self.assertEqual(usage_range(None, None, today=date(2026, 10, 28)), (date(2026, 9, 29), date(2026, 10, 28)))
        self.assertEqual(usage_range(None, "2026-10-10", today=date(2026, 10, 28)), (date(2026, 9, 11), date(2026, 10, 10)))

    def test_a_year_and_a_day_is_the_most(self):
        self.assertEqual(usage_range("2025-10-28", "2026-10-28"), (date(2025, 10, 28), date(2026, 10, 28)))
        with self.assertRaises(RangeError):
            usage_range("2025-10-27", "2026-10-28")
