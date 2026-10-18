from copy import deepcopy
from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APITestCase

from apps.admin.analytics_serializers import EmailDeliveryAnalyticsResponseSerializer
from apps.admin.analytics_views import EmailDeliveryAnalyticsView
from apps.announcements.models import (
    Announcement,
    AnnouncementAudience,
    AnnouncementDelivery,
)
from apps.groups.models import Groups
from apps.resources.models import Roles
from apps.services.models import EmailDeliveryMetric
from apps.users.models import AdminScope


class EmailDeliveryAnalyticsSchemaTests(SimpleTestCase):
    def test_openapi_schema_documents_complete_response_contract(self):
        schema = SchemaGenerator(
            patterns=[
                path(
                    "api/v1/admin/analytics/email/",
                    EmailDeliveryAnalyticsView.as_view(),
                )
            ]
        ).get_schema(request=None, public=True)

        operation = schema["paths"]["/api/v1/admin/analytics/email/"]["get"]
        response_schema = operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        self.assertEqual(
            response_schema["$ref"],
            "#/components/schemas/EmailDeliveryAnalyticsResponse",
        )

        components = schema["components"]["schemas"]
        opened = components["EmailDeliveryStatusByRole"]["properties"]["opened"]
        self.assertTrue(opened["nullable"])
        self.assertEqual(opened["minimum"], 0)
        attempted = components["EmailDeliveryTotals"]["properties"]["attempted"]
        self.assertEqual(attempted["minimum"], 0)


class EmailDeliveryAnalyticsApiTests(APITestCase):
    url = "/api/v1/admin/analytics/email/"
    primary_mailbox = "info@biotechfutures.org"
    secondary_mailbox = "connect@biotechfutures.org"
    quota_limit = 3000
    zero_totals = {
        "attempted": 0,
        "delivered": 0,
        "failed": 0,
        "delivery_runs": 0,
    }
    snapshot_at = datetime(2026, 9, 15, 12, tzinfo=datetime_timezone.utc)

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="email.analytics.admin@example.com",
            password="pass123",
            first_name="Ada",
            last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin)
        self.reader = User.objects.create_user(
            email="email.analytics.reader@example.com",
            password="pass123",
            first_name="Regular",
            last_name="Reader",
        )
        self.announcement = Announcement.objects.create(
            author_user=self.admin,
            title="Analytics update",
            body="Delivery analytics contract fixture",
            visibility_scope=Announcement.VisibilityScope.GLOBAL,
        )
        self.roles = {}
        for role_name in ("student", "mentor", "supervisor", "admin"):
            role = Roles.objects.filter(role_name__iexact=role_name).first()
            if role is None:
                role = Roles.objects.create(role_name=role_name)
            self.roles[role_name] = role

    def delivery(
        self,
        *,
        started_at,
        recipients,
        delivered,
        failed,
        delivery_status,
        initiated_by=None,
        announcement=None,
        source_mailbox=None,
    ):
        values = {
            "announcement": announcement or self.announcement,
            "initiated_by": initiated_by,
            "started_at": started_at,
            "completed_at": started_at + timedelta(minutes=1),
            "status": delivery_status,
            "recipient_count": recipients,
            "success_count": delivered,
            "failure_count": failed,
        }
        delivery = AnnouncementDelivery.objects.create(
            **values,
        )
        EmailDeliveryMetric.objects.create(
            email_type="announcement",
            source_mailbox=source_mailbox or self.primary_mailbox,
            attempted_count=recipients,
            delivered_count=delivered,
            failed_count=failed,
            status=delivery_status,
            initiated_by=initiated_by,
            started_at=started_at,
            completed_at=started_at + timedelta(minutes=1),
        )
        return delivery

    def targeted_announcement(self, title, *audiences):
        announcement = Announcement.objects.create(
            author_user=self.admin,
            title=title,
            body="Role analytics fixture",
            visibility_scope=Announcement.VisibilityScope.ROLE_BASED,
        )
        for audience in audiences:
            AnnouncementAudience.objects.create(
                announcement=announcement,
                role=audience.get("role"),
                group=audience.get("group"),
            )
        return announcement

    @staticmethod
    def empty_status_by_role():
        return [
            {
                "role": role,
                "attempted": 0,
                "delivered": 0,
                "failed": 0,
                "tracked_deliveries": 0,
                "opened": None,
            }
            for role in ("Student", "Mentor", "Supervisor")
        ]

    def get_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        with patch(
            "apps.admin.services.analytics.timezone.now",
            return_value=self.snapshot_at,
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["msg"],
            "Email delivery analytics retrieved successfully",
        )
        return response.data["data"]

    def test_requires_authentication_and_admin_scope(self):
        anonymous_response = self.client.get(self.url)
        self.assertIn(
            anonymous_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

        self.client.force_authenticate(user=self.reader)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_dataset_contract_exposes_both_configured_mailboxes(self):
        data = self.get_as_admin()

        self.assertEqual(
            data,
            {
                "snapshot_at": self.snapshot_at.isoformat(),
                "mailboxes": [
                    {
                        "email": self.primary_mailbox,
                        "quota_limit": self.quota_limit,
                        "totals": self.zero_totals,
                        "hourly": [],
                        "daily": [],
                    },
                    {
                        "email": self.secondary_mailbox,
                        "quota_limit": self.quota_limit,
                        "totals": self.zero_totals,
                        "hourly": [],
                        "daily": [],
                    },
                ],
                "mailbox": self.primary_mailbox,
                "quota_limit": self.quota_limit,
                "totals": self.zero_totals,
                "hourly": [],
                "daily": [],
                "status_by_role": self.empty_status_by_role(),
                "role_attribution": {
                    "basis": "current_single_role_audience",
                    "available": False,
                    "complete": False,
                    "tracked_delivery_runs": 0,
                    "unattributed_delivery_runs": 0,
                    "tracked_attempted": 0,
                    "unattributed_attempted": 0,
                    "tracked_delivered": 0,
                    "unattributed_delivered": 0,
                    "tracked_failed": 0,
                    "unattributed_failed": 0,
                },
                "recent_deliveries": [],
                "recent_sends": [],
            },
        )

    def test_recent_sends_cover_every_email_type_newest_first(self):
        announced = self.delivery(
            started_at=self.snapshot_at - timedelta(hours=3),
            recipients=4,
            delivered=3,
            failed=1,
            delivery_status=AnnouncementDelivery.Status.PARTIAL,
            initiated_by=self.admin,
        )
        EmailDeliveryMetric.objects.create(
            email_type="password_reset",
            source_mailbox=self.primary_mailbox,
            attempted_count=1,
            delivered_count=1,
            failed_count=0,
            status=EmailDeliveryMetric.Status.SUCCESS,
            started_at=self.snapshot_at - timedelta(hours=1),
            completed_at=self.snapshot_at - timedelta(hours=1),
        )
        EmailDeliveryMetric.objects.create(
            email_type="custom_bulk_send",
            source_mailbox=self.secondary_mailbox,
            attempted_count=2,
            delivered_count=0,
            failed_count=2,
            status=EmailDeliveryMetric.Status.FAILED,
            started_at=self.snapshot_at - timedelta(days=30),
            completed_at=self.snapshot_at - timedelta(days=30),
        )

        sends = self.get_as_admin()["recent_sends"]

        self.assertEqual(
            [(row["email_type"], row["email_type_label"]) for row in sends],
            [
                ("password_reset", "Password reset"),
                ("announcement", "Announcement notification"),
                ("custom_bulk_send", "Custom bulk send"),
            ],
        )
        self.assertIsNone(sends[0]["title"])
        self.assertEqual(sends[0]["initiated_by_name"], "System")
        self.assertEqual(sends[1]["title"], "Analytics update")
        self.assertEqual(sends[1]["announcement_id"], announced.announcement_id)
        self.assertEqual(
            (sends[1]["status"], sends[1]["attempted"], sends[1]["delivered"], sends[1]["failed"]),
            ("partial", 4, 3, 1),
        )
        self.assertEqual(sends[1]["initiated_by_email"], self.admin.email)
        self.assertEqual(sends[2]["source_mailbox"], self.secondary_mailbox)

    @patch("apps.admin.services.analytics.RECENT_SENDS_PER_TYPE", 2)
    def test_recent_sends_keep_each_types_latest_sends(self):
        self.delivery(
            started_at=self.snapshot_at - timedelta(days=10),
            recipients=4,
            delivered=4,
            failed=0,
            delivery_status=AnnouncementDelivery.Status.SUCCESS,
        )
        for hours in (1, 2, 3):
            EmailDeliveryMetric.objects.create(
                email_type="login_code",
                source_mailbox=self.primary_mailbox,
                attempted_count=1,
                delivered_count=1,
                failed_count=0,
                status=EmailDeliveryMetric.Status.SUCCESS,
                started_at=self.snapshot_at - timedelta(hours=hours),
                completed_at=self.snapshot_at - timedelta(hours=hours),
            )

        sends = self.get_as_admin()["recent_sends"]

        # Newer login codes beyond their own limit do not crowd out the announcement.
        self.assertEqual(
            [(row["email_type"], datetime.fromisoformat(row["started_at"])) for row in sends],
            [
                ("login_code", self.snapshot_at - timedelta(hours=1)),
                ("login_code", self.snapshot_at - timedelta(hours=2)),
                ("announcement", self.snapshot_at - timedelta(days=10)),
            ],
        )
        self.assertEqual(sends[2]["title"], "Analytics update")

    def test_response_serializer_allows_null_opened_and_rejects_negative_counts(self):
        payload = {
            "msg": "Email delivery analytics retrieved successfully",
            "data": self.get_as_admin(),
        }
        serializer = EmailDeliveryAnalyticsResponseSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(
            serializer.validated_data["data"]["status_by_role"][0]["opened"]
        )

        invalid_payload = deepcopy(payload)
        invalid_payload["data"]["status_by_role"][0]["attempted"] = -1
        invalid_serializer = EmailDeliveryAnalyticsResponseSerializer(
            data=invalid_payload
        )

        self.assertFalse(invalid_serializer.is_valid())
        self.assertIn(
            "attempted",
            invalid_serializer.errors["data"]["status_by_role"][0],
        )

    def test_mailboxes_use_their_own_persisted_delivery_counts(self):
        latest = datetime(2026, 9, 15, 12, tzinfo=datetime_timezone.utc)
        inside_window = latest - timedelta(hours=24) + timedelta(seconds=1)
        exact_excluded_boundary = latest - timedelta(hours=24)

        latest_delivery = self.delivery(
            started_at=latest,
            recipients=5,
            delivered=4,
            failed=1,
            delivery_status=AnnouncementDelivery.Status.PARTIAL,
            initiated_by=self.admin,
        )
        inside_delivery = self.delivery(
            started_at=inside_window,
            recipients=3,
            delivered=3,
            failed=0,
            delivery_status=AnnouncementDelivery.Status.SUCCESS,
            initiated_by=self.admin,
        )
        secondary_delivery = self.delivery(
            started_at=latest - timedelta(hours=2),
            recipients=2,
            delivered=2,
            failed=0,
            delivery_status=AnnouncementDelivery.Status.SUCCESS,
            initiated_by=self.admin,
            source_mailbox=self.secondary_mailbox,
        )
        boundary_delivery = self.delivery(
            started_at=exact_excluded_boundary,
            recipients=7,
            delivered=0,
            failed=7,
            delivery_status=AnnouncementDelivery.Status.FAILED,
        )

        data = self.get_as_admin()

        self.assertEqual(data["snapshot_at"], latest.isoformat())
        self.assertEqual(len(data["mailboxes"]), 2)
        primary, secondary = data["mailboxes"]
        self.assertEqual(primary["email"], self.primary_mailbox)
        self.assertEqual(primary["quota_limit"], self.quota_limit)
        self.assertEqual(
            primary["totals"],
            {
                "attempted": 8,
                "delivered": 7,
                "failed": 1,
                "delivery_runs": 2,
            },
        )
        self.assertEqual(
            [row["attempted"] for row in primary["hourly"]],
            [3, 5],
        )
        self.assertEqual(
            primary["daily"],
            [
                {
                    "date": "2026-09-14",
                    "attempted": 10,
                    "delivered": 3,
                    "failed": 7,
                },
                {
                    "date": "2026-09-15",
                    "attempted": 5,
                    "delivered": 4,
                    "failed": 1,
                },
            ],
        )
        self.assertEqual(secondary["email"], self.secondary_mailbox)
        self.assertEqual(
            secondary["totals"],
            {"attempted": 2, "delivered": 2, "failed": 0, "delivery_runs": 1},
        )
        self.assertEqual([row["attempted"] for row in secondary["hourly"]], [2])

        # Legacy top-level fields contain the combined mailbox totals.
        self.assertEqual(data["mailbox"], self.primary_mailbox)
        self.assertEqual(data["quota_limit"], self.quota_limit)
        self.assertEqual(
            data["totals"],
            {"attempted": 10, "delivered": 9, "failed": 1, "delivery_runs": 3},
        )
        self.assertEqual(data["status_by_role"], self.empty_status_by_role())
        self.assertEqual(
            data["role_attribution"],
            {
                "basis": "current_single_role_audience",
                "available": False,
                "complete": False,
                "tracked_delivery_runs": 0,
                "unattributed_delivery_runs": 3,
                "tracked_attempted": 0,
                "unattributed_attempted": 10,
                "tracked_delivered": 0,
                "unattributed_delivered": 9,
                "tracked_failed": 0,
                "unattributed_failed": 1,
            },
        )

        recent = data["recent_deliveries"]
        self.assertEqual(
            [row["id"] for row in recent],
            [
                latest_delivery.id,
                secondary_delivery.id,
                inside_delivery.id,
                boundary_delivery.id,
            ],
        )
        self.assertEqual(recent[0]["announcement_id"], self.announcement.id)
        self.assertEqual(recent[0]["title"], "Analytics update")
        self.assertEqual(recent[0]["status"], AnnouncementDelivery.Status.PARTIAL)
        self.assertEqual(recent[0]["initiated_by_name"], "Ada Admin")
        self.assertEqual(recent[0]["initiated_by_email"], self.admin.email)
        self.assertEqual(recent[-1]["initiated_by_name"], "System")
        self.assertEqual(recent[-1]["initiated_by_email"], "")

    def test_twenty_four_hour_window_excludes_exact_lower_boundary(self):
        latest = datetime(2026, 9, 15, 12, tzinfo=datetime_timezone.utc)
        announcement = self.targeted_announcement(
            "Student update",
            {"role": self.roles["student"]},
        )
        self.delivery(
            started_at=latest,
            recipients=2,
            delivered=2,
            failed=0,
            delivery_status=AnnouncementDelivery.Status.SUCCESS,
            announcement=announcement,
        )
        self.delivery(
            started_at=latest - timedelta(hours=24),
            recipients=99,
            delivered=99,
            failed=0,
            delivery_status=AnnouncementDelivery.Status.SUCCESS,
            announcement=announcement,
        )

        data = self.get_as_admin()

        self.assertEqual(
            data["totals"],
            {
                "attempted": 2,
                "delivered": 2,
                "failed": 0,
                "delivery_runs": 1,
            },
        )
        self.assertEqual(sum(row["attempted"] for row in data["hourly"]), 2)
        self.assertEqual(
            data["status_by_role"][0],
            {
                "role": "Student",
                "attempted": 2,
                "delivered": 2,
                "failed": 0,
                "tracked_deliveries": 1,
                "opened": None,
            },
        )
        self.assertEqual(
            data["role_attribution"],
            {
                "basis": "current_single_role_audience",
                "available": True,
                "complete": True,
                "tracked_delivery_runs": 1,
                "unattributed_delivery_runs": 0,
                "tracked_attempted": 2,
                "unattributed_attempted": 0,
                "tracked_delivered": 2,
                "unattributed_delivered": 0,
                "tracked_failed": 0,
                "unattributed_failed": 0,
            },
        )

    def test_role_status_tracks_each_single_supported_role(self):
        latest = datetime(2026, 9, 15, 12, tzinfo=datetime_timezone.utc)
        fixtures = [
            ("student", 6, 5, 1, AnnouncementDelivery.Status.PARTIAL),
            ("mentor", 4, 4, 0, AnnouncementDelivery.Status.SUCCESS),
            ("supervisor", 3, 0, 3, AnnouncementDelivery.Status.FAILED),
        ]
        for index, fixture in enumerate(fixtures):
            role_name, attempted, delivered, failed, delivery_status = fixture
            announcement = self.targeted_announcement(
                f"{role_name.title()} update",
                {"role": self.roles[role_name]},
            )
            self.delivery(
                started_at=latest - timedelta(hours=index),
                recipients=attempted,
                delivered=delivered,
                failed=failed,
                delivery_status=delivery_status,
                announcement=announcement,
            )

        data = self.get_as_admin()

        self.assertEqual(
            data["status_by_role"],
            [
                {
                    "role": "Student",
                    "attempted": 6,
                    "delivered": 5,
                    "failed": 1,
                    "tracked_deliveries": 1,
                    "opened": None,
                },
                {
                    "role": "Mentor",
                    "attempted": 4,
                    "delivered": 4,
                    "failed": 0,
                    "tracked_deliveries": 1,
                    "opened": None,
                },
                {
                    "role": "Supervisor",
                    "attempted": 3,
                    "delivered": 0,
                    "failed": 3,
                    "tracked_deliveries": 1,
                    "opened": None,
                },
            ],
        )
        self.assertEqual(
            data["role_attribution"],
            {
                "basis": "current_single_role_audience",
                "available": True,
                "complete": True,
                "tracked_delivery_runs": 3,
                "unattributed_delivery_runs": 0,
                "tracked_attempted": 13,
                "unattributed_attempted": 0,
                "tracked_delivered": 9,
                "unattributed_delivered": 0,
                "tracked_failed": 4,
                "unattributed_failed": 0,
            },
        )

    def test_role_status_reports_ambiguous_delivery_coverage_as_unattributed(self):
        latest = datetime(2026, 9, 15, 12, tzinfo=datetime_timezone.utc)
        group = Groups.objects.create(group_name="Email analytics group")
        student = self.roles["student"]

        tracked = self.targeted_announcement("Tracked", {"role": student})
        mixed = self.targeted_announcement(
            "Mixed row",
            {"role": student, "group": group},
        )
        group_only = self.targeted_announcement("Group", {"group": group})
        multiple_roles = self.targeted_announcement(
            "Multiple roles",
            {"role": student},
            {"role": self.roles["mentor"]},
        )
        unsupported = self.targeted_announcement(
            "Unsupported role",
            {"role": self.roles["admin"]},
        )
        announcements = [
            (tracked, 2),
            (mixed, 3),
            (group_only, 4),
            (multiple_roles, 5),
            (unsupported, 6),
            (self.announcement, 7),
        ]
        for index, (announcement, attempted) in enumerate(announcements):
            self.delivery(
                started_at=latest - timedelta(hours=index),
                recipients=attempted,
                delivered=attempted,
                failed=0,
                delivery_status=AnnouncementDelivery.Status.SUCCESS,
                announcement=announcement,
            )

        data = self.get_as_admin()

        self.assertEqual(
            data["status_by_role"][0],
            {
                "role": "Student",
                "attempted": 2,
                "delivered": 2,
                "failed": 0,
                "tracked_deliveries": 1,
                "opened": None,
            },
        )
        self.assertEqual(data["status_by_role"][1:], self.empty_status_by_role()[1:])
        self.assertEqual(
            data["role_attribution"],
            {
                "basis": "current_single_role_audience",
                "available": True,
                "complete": False,
                "tracked_delivery_runs": 1,
                "unattributed_delivery_runs": 5,
                "tracked_attempted": 2,
                "unattributed_attempted": 25,
                "tracked_delivered": 2,
                "unattributed_delivered": 25,
                "tracked_failed": 0,
                "unattributed_failed": 0,
            },
        )
        self.assertEqual(
            data["role_attribution"]["tracked_attempted"]
            + data["role_attribution"]["unattributed_attempted"],
            data["totals"]["attempted"],
        )
        self.assertEqual(
            data["role_attribution"]["tracked_delivered"]
            + data["role_attribution"]["unattributed_delivered"],
            data["totals"]["delivered"],
        )
        self.assertEqual(
            data["role_attribution"]["tracked_failed"]
            + data["role_attribution"]["unattributed_failed"],
            data["totals"]["failed"],
        )

    def test_only_get_is_allowed_and_disallowed_methods_do_not_write(self):
        self.client.force_authenticate(user=self.admin)

        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url, {}, format="json")
                self.assertEqual(
                    response.status_code,
                    status.HTTP_405_METHOD_NOT_ALLOWED,
                )

        self.assertFalse(AnnouncementDelivery.objects.exists())
