from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.resources.models import ResourceAccessEvent, Resources
from apps.users.models import AdminScope


class ResourceAccessTrackingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="reader@example.com", password="pass123",
            first_name="Resource", last_name="Reader",
        )
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pass123",
            first_name="Resource", last_name="Owner",
        )
        self.resource = Resources.objects.create(
            name="Guide", description="Resource access tracking guide",
            uploaded_by=self.owner,
            visibility_scope=Resources.VisibilityScope.PUBLIC,
            storage_key="https://example.com/guide.pdf",
        )
        self.url = reverse("resource-files-access", kwargs={"pk": self.resource.pk})
        self.client.force_authenticate(self.user)

    def test_authenticated_access_records_correct_user_resource_and_timestamp(self):
        before = timezone.now()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        event = ResourceAccessEvent.objects.get()
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.resource, self.resource)
        self.assertGreaterEqual(event.created_at, before)
        self.assertLessEqual(event.created_at, timezone.now())

    def test_repeated_accesses_are_separate_events(self):
        for _ in range(2):
            self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(ResourceAccessEvent.objects.count(), 2)

    def test_metadata_and_analytics_reads_do_not_record_events(self):
        AdminScope.objects.create(user=self.user)
        for url in (
            reverse("resource-files-list"),
            reverse("resource-files-detail", kwargs={"pk": self.resource.pk}),
            reverse("resource-types-list"),
            "/api/v1/admin/analytics/group-activity/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertFalse(ResourceAccessEvent.objects.exists())

    def test_download_after_access_does_not_double_count(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        response = self.client.get(reverse("resource-files-download", kwargs={"pk": self.resource.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.resource.storage_key)
        self.assertEqual(ResourceAccessEvent.objects.count(), 1)

    def test_options_does_not_record_events(self):
        self.assertEqual(self.client.options(self.url).status_code, 200)
        self.assertFalse(ResourceAccessEvent.objects.exists())

    def test_unauthenticated_access_does_not_record_event(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
        self.assertFalse(ResourceAccessEvent.objects.exists())

    def test_forbidden_access_does_not_record_event(self):
        self.resource.visibility_scope = Resources.VisibilityScope.ROLE
        self.resource.save(update_fields=["visibility_scope"])
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertFalse(ResourceAccessEvent.objects.exists())

    def test_deleted_resource_does_not_record_event(self):
        self.resource.deleted_at = timezone.now()
        self.resource.save(update_fields=["deleted_at"])
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertFalse(ResourceAccessEvent.objects.exists())

    def test_interaction_does_not_require_content_to_load(self):
        self.resource.storage_key = None
        self.resource.save(update_fields=["storage_key"])
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(ResourceAccessEvent.objects.count(), 1)

    def test_missing_resource_does_not_record_event(self):
        url = reverse("resource-files-access", kwargs={"pk": self.resource.pk + 999})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse(ResourceAccessEvent.objects.exists())
