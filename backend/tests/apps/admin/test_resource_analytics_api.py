from datetime import datetime, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.urls import path
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APITestCase

from apps.admin.analytics_views import ResourceAnalyticsView
from apps.resources.models import ResourceAccessEvent, Resources, ResourceType
from apps.users.models import AdminScope


class ResourceAnalyticsSchemaTests(SimpleTestCase):
    def test_schema_documents_dates_and_response(self):
        schema = SchemaGenerator(patterns=[
            path("api/v1/admin/analytics/resources/", ResourceAnalyticsView.as_view()),
        ]).get_schema(request=None, public=True)
        operation = schema["paths"]["/api/v1/admin/analytics/resources/"]["get"]
        parameters = {item["name"]: item for item in operation["parameters"]}
        self.assertEqual(set(parameters), {"start", "end"})
        for parameter in parameters.values():
            self.assertFalse(parameter.get("required", False))
            self.assertEqual(parameter["schema"]["format"], "date")
            self.assertIn("resource interactions", parameter["description"])
        self.assertIn("200", operation["responses"])


class ResourceAnalyticsApiTests(APITestCase):
    url = "/api/v1/admin/analytics/resources/"

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pass123", first_name="Admin", last_name="User",
        )
        AdminScope.objects.create(user=self.admin)
        self.reader = User.objects.create_user(
            email="reader@example.com", password="pass123", first_name="Reader", last_name="User",
        )
        self.category = ResourceType.objects.create(type_name="Guide")
        self.first = Resources.objects.create(
            name="First", description="First guide", uploaded_by=self.admin, type=self.category,
        )
        self.second = Resources.objects.create(
            name="Second", description="Second guide", uploaded_by=self.admin, type=self.category,
        )
        self.uncategorized = Resources.objects.create(
            name="Other", description="No category", uploaded_by=self.admin,
        )
        self.client.force_authenticate(user=self.admin)

    def event(self, resource, user, timestamp):
        return ResourceAccessEvent.objects.create(
            resource=resource, user=user,
            created_at=datetime.fromisoformat(timestamp).replace(tzinfo=datetime_timezone.utc),
        )

    def seed_events(self):
        self.event(self.second, self.reader, "2026-08-29T23:59:59")
        self.event(self.first, self.reader, "2026-08-30T00:00:00")
        self.event(self.first, self.reader, "2026-08-30T12:00:00")
        self.event(self.uncategorized, self.admin, "2026-08-30T23:59:59")
        self.event(self.first, self.admin, "2026-08-31T00:00:00")

    def data(self, params=None):
        response = self.client.get(self.url, params or {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["msg"], "Resource analytics retrieved successfully")
        return response.data["data"]

    def test_authentication_and_admin_permission(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
        self.client.force_authenticate(user=self.reader)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_empty_dataset(self):
        self.assertEqual(self.data(), {
            "total_clicks": 0, "unique_users": 0, "active_resources": 0,
            "clicks_by_day": [], "top_resources": [], "clicks_by_category": [],
            "query_range": {"start": None, "end": None},
        })

    def test_totals_count_events_and_distinct_users_and_resources(self):
        self.seed_events()
        data = self.data()
        self.assertEqual(data["total_clicks"], 5)
        self.assertEqual(data["unique_users"], 2)
        self.assertEqual(data["active_resources"], 3)
        self.assertEqual(ResourceAccessEvent.objects.count(), 5)

    def test_daily_grouping_is_ordered(self):
        self.seed_events()
        self.assertEqual(self.data()["clicks_by_day"], [
            {"date": "2026-08-29", "click_count": 1},
            {"date": "2026-08-30", "click_count": 3},
            {"date": "2026-08-31", "click_count": 1},
        ])

    def test_top_resources_have_stable_tie_order(self):
        self.seed_events()
        self.assertEqual(self.data()["top_resources"], [
            {"resource_id": self.first.id, "resource_name": "First", "click_count": 3, "unique_users": 2},
            {"resource_id": self.second.id, "resource_name": "Second", "click_count": 1, "unique_users": 1},
            {"resource_id": self.uncategorized.id, "resource_name": "Other", "click_count": 1, "unique_users": 1},
        ])

    def test_categories_include_uncategorized_and_use_current_type(self):
        self.seed_events()
        self.assertEqual(self.data()["clicks_by_category"], [
            {"category_id": self.category.id, "category_name": "Guide", "click_count": 4},
            {"category_id": None, "category_name": None, "click_count": 1},
        ])
        self.first.type = None
        self.first.save(update_fields=["type"])
        self.assertEqual(self.data()["clicks_by_category"], [
            {"category_id": None, "category_name": None, "click_count": 4},
            {"category_id": self.category.id, "category_name": "Guide", "click_count": 1},
        ])

    def test_inclusive_dates_filter_every_metric(self):
        self.seed_events()
        data = self.data({"start": "2026-08-30", "end": "2026-08-30"})
        self.assertEqual(data, {
            "total_clicks": 3, "unique_users": 2, "active_resources": 2,
            "clicks_by_day": [{"date": "2026-08-30", "click_count": 3}],
            "top_resources": [
                {"resource_id": self.first.id, "resource_name": "First", "click_count": 2, "unique_users": 1},
                {"resource_id": self.uncategorized.id, "resource_name": "Other", "click_count": 1, "unique_users": 1},
            ],
            "clicks_by_category": [
                {"category_id": self.category.id, "category_name": "Guide", "click_count": 2},
                {"category_id": None, "category_name": None, "click_count": 1},
            ],
            "query_range": {"start": "2026-08-30", "end": "2026-08-30"},
        })

    def test_single_sided_bounds_and_empty_period(self):
        self.seed_events()
        for params, count in (({"start": "2026-08-30"}, 4), ({"end": "2026-08-29"}, 1)):
            with self.subTest(params=params):
                data = self.data(params)
                self.assertEqual(data["total_clicks"], count)
                self.assertEqual(data["query_range"], {"start": params.get("start"), "end": params.get("end")})
        data = self.data({"start": "2027-01-01"})
        self.assertEqual((data["total_clicks"], data["unique_users"], data["active_resources"]), (0, 0, 0))
        for field in ("clicks_by_day", "top_resources", "clicks_by_category"):
            self.assertEqual(data[field], [])

    def test_invalid_dates(self):
        for params, field in (
            ({"start": "30-08-2026"}, "start"),
            ({"end": "2026-02-30"}, "end"),
            ({"start": "2026-08-31", "end": "2026-08-30"}, "end"),
        ):
            with self.subTest(params=params):
                response = self.client.get(self.url, params)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data["fields"])

    def test_soft_deleted_resources_keep_historical_events(self):
        self.seed_events()
        self.first.deleted_at = timezone.now()
        self.first.save(update_fields=["deleted_at"])
        self.assertEqual(self.data()["total_clicks"], 5)
        self.assertEqual(self.data()["active_resources"], 3)

    def test_filtering_and_grouping_share_current_timezone(self):
        self.event(self.first, self.reader, "2026-08-29T23:00:00")
        with timezone.override("Australia/Sydney"):
            data = self.data({"start": "2026-08-30", "end": "2026-08-30"})
        self.assertEqual(data["total_clicks"], 1)
        self.assertEqual(data["clicks_by_day"], [{"date": "2026-08-30", "click_count": 1}])

    def test_read_only(self):
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 405)
        self.assertFalse(ResourceAccessEvent.objects.exists())
