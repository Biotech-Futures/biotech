from datetime import datetime, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.urls import path
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APITestCase

from apps.admin.analytics_views import GroupActivityAnalyticsView
from apps.chat.models import Messages
from apps.groups.models import GroupMembership, Groups
from apps.users.models import AdminScope


User = get_user_model()


class GroupActivityAnalyticsSchemaTests(SimpleTestCase):
    def test_openapi_schema_documents_date_query_parameters(self):
        schema = SchemaGenerator(
            patterns=[
                path(
                    "api/v1/admin/analytics/group-activity/",
                    GroupActivityAnalyticsView.as_view(),
                )
            ]
        ).get_schema(request=None, public=True)

        operation = schema["paths"][
            "/api/v1/admin/analytics/group-activity/"
        ]["get"]
        parameters = {item["name"]: item for item in operation["parameters"]}

        self.assertEqual(set(parameters), {"start", "end"})
        for parameter in parameters.values():
            self.assertEqual(parameter["in"], "query")
            self.assertFalse(parameter.get("required", False))
            self.assertEqual(parameter["schema"]["type"], "string")
            self.assertEqual(parameter["schema"]["format"], "date")
        self.assertIn("on or after", parameters["start"]["description"])
        self.assertIn("on or before", parameters["end"]["description"])


class GroupActivityAnalyticsApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="analytics.admin@example.com",
            password="pass123",
            first_name="Analytics",
            last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin)
        self.user = User.objects.create_user(
            email="analytics.user@example.com",
            password="pass123",
            first_name="Analytics",
            last_name="User",
        )
        self.student_without_messages = User.objects.create_user(
            email="analytics.student@example.com",
            password="pass123",
            first_name="No",
            last_name="Messages",
        )
        self.mentor = User.objects.create_user(
            email="analytics.mentor@example.com",
            password="pass123",
            first_name="Active",
            last_name="Mentor",
        )
        self.group = Groups.objects.create(group_name="BTF1")
        self.empty_group = Groups.objects.create(group_name="BTF2")
        self.deleted_group = Groups.objects.create(group_name="BTF3")
        self.deleted_group.deleted_at = timezone.now()
        self.deleted_group.save(update_fields=["deleted_at"])

        GroupMembership.objects.create(
            group=self.group,
            user=self.user,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        GroupMembership.objects.create(
            group=self.empty_group,
            user=self.student_without_messages,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        GroupMembership.objects.create(
            group=self.group,
            user=self.mentor,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        # Each mentor assignment represents one group's mentor-to-student ratio.
        GroupMembership.objects.create(
            group=self.empty_group,
            user=self.mentor,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )

        Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text="one",
            sent_at=datetime(2026, 8, 29, 12, tzinfo=datetime_timezone.utc),
        )
        Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text="two",
            sent_at=datetime(2026, 8, 30, 0, tzinfo=datetime_timezone.utc),
        )
        Messages.objects.create(
            group=self.group,
            sender_user=self.mentor,
            message_text="mentor",
            sent_at=datetime(2026, 8, 30, 23, 59, tzinfo=datetime_timezone.utc),
        )
        deleted_message = Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text="deleted",
        )
        deleted_message.soft_delete()
        Messages.objects.create(
            group=self.deleted_group,
            sender_user=self.mentor,
            message_text="deleted group",
        )
        self.url = "/api/v1/admin/analytics/group-activity/"

    def test_admin_can_get_group_activity_analytics(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["msg"],
            "Group activity analytics retrieved successfully",
        )
        self.assertEqual(
            response.data["data"]["messages_by_group"],
            [
                {"group_id": self.group.id, "group_name": "BTF1", "message_count": 3},
                {
                    "group_id": self.empty_group.id,
                    "group_name": "BTF2",
                    "message_count": 0,
                },
            ],
        )
        messages_by_user = {
            row["user_id"]: row for row in response.data["data"]["messages_by_user"]
        }
        self.assertEqual(messages_by_user[self.user.id]["message_count"], 2)
        self.assertEqual(messages_by_user[self.mentor.id]["message_count"], 1)
        self.assertEqual(
            messages_by_user[self.student_without_messages.id]["message_count"], 0
        )
        self.assertNotIn(self.admin.id, messages_by_user)
        self.assertEqual(
            response.data["data"]["messages_by_day"],
            [
                {"date": "2026-08-29", "message_count": 1},
                {"date": "2026-08-30", "message_count": 2},
            ],
        )
        self.assertEqual(
            response.data["data"]["messages_by_group_by_day"],
            [
                {
                    "date": "2026-08-29",
                    "group_id": self.group.id,
                    "group_name": "BTF1",
                    "message_count": 1,
                },
                {
                    "date": "2026-08-30",
                    "group_id": self.group.id,
                    "group_name": "BTF1",
                    "message_count": 2,
                },
            ],
        )
        self.assertEqual(
            response.data["data"]["messages_by_user_by_group_by_day"],
            [
                {
                    "date": "2026-08-29",
                    "user_id": self.user.id,
                    "name": "Analytics User",
                    "group_id": self.group.id,
                    "group_name": "BTF1",
                    "message_count": 1,
                },
                {
                    "date": "2026-08-30",
                    "user_id": self.user.id,
                    "name": "Analytics User",
                    "group_id": self.group.id,
                    "group_name": "BTF1",
                    "message_count": 1,
                },
                {
                    "date": "2026-08-30",
                    "user_id": self.mentor.id,
                    "name": "Active Mentor",
                    "group_id": self.group.id,
                    "group_name": "BTF1",
                    "message_count": 1,
                },
            ],
        )
        self.assertEqual(response.data["data"]["mentor_count"], 1)
        self.assertEqual(response.data["data"]["student_count"], 2)
        self.assertEqual(response.data["data"]["students_per_mentor"], 1.0)
        self.assertEqual(
            response.data["data"]["query_range"],
            {"start": None, "end": None},
        )

    def test_non_admin_cannot_get_group_activity_analytics(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_group_activity_analytics_is_read_only(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_students_per_mentor_is_null_when_there_are_no_mentors(self):
        GroupMembership.objects.filter(
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR
        ).delete()
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["mentor_count"], 0)
        self.assertEqual(response.data["data"]["student_count"], 2)
        self.assertIsNone(response.data["data"]["students_per_mentor"])

    def test_average_group_size_is_rebuilt_from_membership_history(self):
        previous_group = Groups.objects.create(
            group_name="Historical group",
            year=2025,
            created_at=datetime(2025, 1, 1, tzinfo=datetime_timezone.utc),
            deleted_at=datetime(2026, 1, 1, tzinfo=datetime_timezone.utc),
        )
        for user in (self.user, self.student_without_messages):
            GroupMembership.objects.create(
                group=previous_group,
                user=user,
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
                joined_at=datetime(2025, 2, 1, tzinfo=datetime_timezone.utc),
                left_at=datetime(2026, 1, 1, tzinfo=datetime_timezone.utc),
            )
        GroupMembership.objects.create(
            group=previous_group,
            user=self.mentor,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
            joined_at=datetime(2025, 2, 1, tzinfo=datetime_timezone.utc),
            left_at=datetime(2026, 1, 1, tzinfo=datetime_timezone.utc),
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url, {"end": "2026-10-15"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        yearly = {
            row["year"]: row
            for row in response.data["data"]["average_group_size_by_year"]
        }
        self.assertEqual(yearly[2025]["group_count"], 1)
        self.assertEqual(yearly[2025]["student_memberships"], 2)
        self.assertEqual(yearly[2025]["average_group_size"], 2.0)
        summaries = {
            row["year"]: row
            for row in response.data["data"]["group_summary_by_year"]
        }
        self.assertEqual(summaries[2025]["groups_with_mentor"], 1)
        self.assertEqual(summaries[2025]["groups_without_mentor"], 0)
        self.assertEqual(summaries[2025]["mentor_count"], 1)
        self.assertEqual(summaries[2025]["student_count"], 2)
        self.assertEqual(summaries[2025]["students_per_mentor"], 2.0)

    def test_date_range_filters_message_counts_inclusively(self):
        Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text="next day boundary",
            sent_at=datetime(2026, 8, 31, 0, tzinfo=datetime_timezone.utc),
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.url,
            {"start": "2026-08-30", "end": "2026-08-30"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["data"]["messages_by_group"],
            [
                {"group_id": self.group.id, "group_name": "BTF1", "message_count": 2},
                {
                    "group_id": self.empty_group.id,
                    "group_name": "BTF2",
                    "message_count": 0,
                },
            ],
        )
        messages_by_user = {
            row["user_id"]: row for row in response.data["data"]["messages_by_user"]
        }
        self.assertEqual(messages_by_user[self.user.id]["message_count"], 1)
        self.assertEqual(messages_by_user[self.mentor.id]["message_count"], 1)
        self.assertEqual(
            response.data["data"]["messages_by_day"],
            [{"date": "2026-08-30", "message_count": 2}],
        )
        self.assertEqual(
            response.data["data"]["messages_by_group_by_day"],
            [
                {
                    "date": "2026-08-30",
                    "group_id": self.group.id,
                    "group_name": "BTF1",
                    "message_count": 2,
                }
            ],
        )
        self.assertEqual(
            response.data["data"]["query_range"],
            {"start": "2026-08-30", "end": "2026-08-30"},
        )

    def test_maximum_end_date_is_supported(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url, {"end": "9999-12-31"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["data"]["query_range"],
            {"start": None, "end": "9999-12-31"},
        )

    def test_mentor_activity_uses_actual_event_dates_and_date_filters(self):
        from apps.audit.models import AuditLog
        from apps.users.models import MentorProfile

        MentorProfile.objects.create(user=self.mentor, institution="Test", mentor_reason="Test")
        for day in (29, 29, 31):
            AuditLog.objects.create(actor_user=self.mentor, entity_type="user",
                                    entity_id=self.mentor.pk, action="login",
                                    created_at=datetime(2026, 8, day, 12, tzinfo=datetime_timezone.utc))
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, {"start": "2026-08-29", "end": "2026-08-30"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["mentor_activity_by_day"], [
            {"mentor_id": self.mentor.pk, "date": "2026-08-29", "messages": 0, "logins": 2},
            {"mentor_id": self.mentor.pk, "date": "2026-08-30", "messages": 1, "logins": 0},
        ])

    def test_daily_message_counts_include_individual_groups(self):
        Messages.objects.create(
            group=self.empty_group,
            sender_user=self.student_without_messages,
            message_text="another group",
            sent_at=datetime(2026, 8, 29, 18, tzinfo=datetime_timezone.utc),
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["data"]["messages_by_day"],
            [
                {"date": "2026-08-29", "message_count": 2},
                {"date": "2026-08-30", "message_count": 2},
            ],
        )
        self.assertEqual(
            response.data["data"]["messages_by_group_by_day"],
            [
                {
                    "date": "2026-08-29",
                    "group_id": self.group.id,
                    "group_name": "BTF1",
                    "message_count": 1,
                },
                {
                    "date": "2026-08-29",
                    "group_id": self.empty_group.id,
                    "group_name": "BTF2",
                    "message_count": 1,
                },
                {
                    "date": "2026-08-30",
                    "group_id": self.group.id,
                    "group_name": "BTF1",
                    "message_count": 2,
                },
            ],
        )

    def test_date_range_allows_one_sided_bounds(self):
        self.client.force_authenticate(user=self.admin)

        from_response = self.client.get(self.url, {"start": "2026-08-30"})
        until_response = self.client.get(self.url, {"end": "2026-08-29"})

        self.assertEqual(from_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            from_response.data["data"]["messages_by_group"][0]["message_count"],
            2,
        )
        self.assertEqual(
            from_response.data["data"]["query_range"],
            {"start": "2026-08-30", "end": None},
        )
        self.assertEqual(until_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            until_response.data["data"]["messages_by_group"][0]["message_count"],
            1,
        )
        self.assertEqual(
            until_response.data["data"]["query_range"],
            {"start": None, "end": "2026-08-29"},
        )

    def test_invalid_date_returns_bad_request(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url, {"start": "30-08-2026"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start", response.data["fields"])

    def test_end_before_start_returns_bad_request(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.url,
            {"start": "2026-08-31", "end": "2026-08-30"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end", response.data["fields"])
