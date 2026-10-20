from datetime import datetime, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APITestCase

from apps.admin.analytics_views import LoginActivityAnalyticsView
from apps.audit.models import AuditLog
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import AdminScope


User = get_user_model()


class LoginActivityAnalyticsSchemaTests(SimpleTestCase):
    def test_openapi_schema_documents_date_parameters(self):
        schema = SchemaGenerator(
            patterns=[
                path(
                    "api/v1/admin/analytics/login-activity/",
                    LoginActivityAnalyticsView.as_view(),
                )
            ]
        ).get_schema(request=None, public=True)

        operation = schema["paths"]["/api/v1/admin/analytics/login-activity/"]["get"]
        self.assertEqual(
            {parameter["name"] for parameter in operation["parameters"]},
            {"start", "end"},
        )


class LoginActivityAnalyticsApiTests(APITestCase):
    url = "/api/v1/admin/analytics/login-activity/"

    def setUp(self):
        self.admin = User.objects.create_user(email="login.admin@example.com")
        AdminScope.objects.create(user=self.admin)
        self.reader = User.objects.create_user(email="login.reader@example.com")
        self.student = self._participant("student@example.com", "student")
        self.mentor = self._participant("mentor@example.com", "mentor")

    def _participant(self, email, role_name):
        user = User.objects.create_user(email=email)
        role, _ = Roles.objects.get_or_create(role_name=role_name)
        RoleAssignmentHistory.objects.create(
            user=user,
            role=role,
            valid_from=datetime(2025, 1, 1, tzinfo=datetime_timezone.utc),
        )
        return user

    def _login(self, user, year, month, day, hour):
        return AuditLog.objects.create(
            actor_user=user,
            entity_type="user",
            entity_id=user.pk,
            action=AuditLog.ActionChoices.LOGIN,
            created_at=datetime(year, month, day, hour, tzinfo=datetime_timezone.utc),
        )

    def test_counts_unique_users_by_utc_day_and_year(self):
        self._login(self.student, 2026, 8, 29, 8)
        self._login(self.student, 2026, 8, 29, 12)
        self._login(self.mentor, 2026, 8, 29, 9)
        self._login(self.student, 2026, 8, 30, 10)
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(
            data["by_day"],
            [
                {
                    "date": "2026-08-29",
                    "students": 1,
                    "mentors": 1,
                    "supervisors": 0,
                    "total": 2,
                },
                {
                    "date": "2026-08-30",
                    "students": 1,
                    "mentors": 0,
                    "supervisors": 0,
                    "total": 1,
                },
            ],
        )
        self.assertEqual(
            data["by_year"],
            [{"year": 2026, "students": 1, "mentors": 1, "supervisors": 0, "total": 2}],
        )
        self.assertEqual(data["active_users"], {"daily": 1, "weekly": 2, "monthly": 2})
        self.assertEqual(
            data["active_user_comparison"],
            {
                "daily": {"current": 1, "previous": 2},
                "weekly": {"current": 2, "previous": 0},
                "monthly": {"current": 2, "previous": 0},
            },
        )
        self.assertEqual(data["latest_activity_date"], "2026-08-30")

    def test_date_filter_is_inclusive_and_excludes_unsupported_roles(self):
        self._login(self.student, 2026, 8, 29, 8)
        self._login(self.student, 2026, 8, 30, 8)
        self._login(self.admin, 2026, 8, 30, 9)
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url, {"start": "2026-08-30", "end": "2026-08-30"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["by_day"][0]["total"], 1)
        self.assertEqual(
            response.data["data"]["query_range"],
            {"start": "2026-08-30", "end": "2026-08-30"},
        )

    def test_requires_admin_and_is_read_only(self):
        self.client.force_authenticate(user=self.reader)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
